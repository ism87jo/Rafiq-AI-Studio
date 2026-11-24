import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from .media import export_movie, probe
from .store import Conflict
from .workflows import build_graph


class Worker:
    def __init__(self, store, engine, voice_python=None):
        self.store = store
        self.engine = engine
        self.voice_python = voice_python
        self.stop_event = threading.Event()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rafiq-render")

    def submit(self, job_id):
        self.executor.submit(self.run, job_id)

    def close(self):
        self.stop_event.set()
        self.executor.shutdown(wait=True, cancel_futures=True)

    def run(self, job_id):
        try:
            job = self.store.transition_job(job_id, "queued", state="running", progress=5)
        except Conflict:
            return
        started = time.monotonic()
        payload = job["payload"]
        project = payload["project"]
        output = self.store.assets / f"{uuid.uuid4().hex}.mp4"
        work = self.store.directory / "work" / job_id
        try:
            if job["kind"] == "generate":
                scene = payload["scene"]
                graph = build_graph(project, scene, reference_name="pending.png", prefix=f"rafiq/{job_id}")
                readiness = self.engine.inspect(graph)
                if not readiness["ready"]:
                    raise ValueError("\n".join(readiness["errors"]))
                if scene["mode"] == "image":
                    reference = self.engine.upload_image(self.store.path(scene["reference_asset_id"], project["id"], "image"))
                    graph = build_graph(project, scene, reference, prefix=f"rafiq/{job_id}")
                self.store.update_job(job_id, graph=graph, progress=10)
                generation_start = time.monotonic()
                output = self.engine.generate(graph, output, lambda prompt_id: self.store.update_job(job_id, prompt_id=prompt_id, progress=15), self.stop_event)
                self.store.update_job(job_id, generation_seconds=time.monotonic() - generation_start)
                metadata = probe(output)
                if not any(s["codec_type"] == "video" for s in metadata["streams"]):
                    raise ValueError("ComfyUI returned a file without a video stream")
                metadata = dict(probe=metadata, provenance="comfyui", seed=scene["seed"], preset=project["settings"]["preset"], job_id=job_id)
                kind = "video"
            elif job["kind"] == "export":
                metadata = dict(probe=export_movie(self.store, project, work, output), provenance="ffmpeg-edit", job_id=job_id)
                kind = "video"
            elif job["kind"] == "voice":
                if not self.voice_python:
                    raise ValueError("Configure RAFIQ_VOICE_PYTHON with an offline Chatterbox environment first")
                output = output.with_suffix(".wav")
                work.mkdir(parents=True, exist_ok=True)
                request_file = work / "request.json"
                request_file.write_text(json.dumps(payload["voice_request"], ensure_ascii=False), encoding="utf-8")
                environment = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
                result = subprocess.run([self.voice_python, str(Path(__file__).with_name("voice_worker.py")), "--request", str(request_file), "--output", str(output)],
                                        env=environment, capture_output=True, text=True, timeout=1800)
                if result.returncode:
                    raise ValueError("Offline voice worker failed. Check cached weights and dependencies.\n" + result.stderr[-1600:])
                metadata = dict(probe=probe(output), provenance="chatterbox-offline", job_id=job_id)
                kind = "audio"
            else:
                raise ValueError("Unknown job kind")
            asset = self.store.add_asset(project["id"], kind, output, f"{job['kind']}-{job_id}{output.suffix}", metadata)
            self.store.update_job(job_id, state="succeeded", progress=100, output_asset_id=asset["id"], elapsed_seconds=time.monotonic() - started)
        except (ValueError, KeyError, OSError, httpx.HTTPError, subprocess.SubprocessError) as exc:
            output.unlink(missing_ok=True)
            self.store.update_job(job_id, state="interrupted" if self.stop_event.is_set() else "failed", error=str(exc), elapsed_seconds=time.monotonic() - started)
        finally:
            shutil.rmtree(work, ignore_errors=True)
