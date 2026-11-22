"""Run one real local ComfyUI shot; never substitutes a fixture or animation."""
import argparse
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .comfy import ComfyClient
from .example import first_chapter
from .models import Project
from .store import Store
from .worker import Worker
from .workflows import PRESETS, build_graph, estimate


def gpu_memory_mb():
    if not shutil.which("nvidia-smi"):
        return None
    result = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
    if result.returncode:
        return None
    return max((float(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()), default=None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=PRESETS, default="wan21-1.3b")
    parser.add_argument("--seconds", type=float, default=1)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=192)
    parser.add_argument("--data-dir", type=Path, default=Path.home() / "RafiqAIStudioBenchmark")
    parser.add_argument("--model-manifest", type=Path)
    parser.add_argument("--run", action="store_true", help="Start the shot on the already-running local GPU")
    args = parser.parse_args()
    project = first_chapter("benchmark-" + uuid.uuid4().hex).model_dump()
    project["scenes"] = project["scenes"][:1]
    project["scenes"][0]["seconds"] = args.seconds
    project["settings"].update(preset=args.preset, width=args.width, height=args.height,
                               steps=args.steps, fps=PRESETS[args.preset]["fps"])
    project = Project.model_validate(project).model_dump()
    engine = ComfyClient(timeout_seconds=1800)
    readiness = engine.inspect(build_graph(project, project["scenes"][0]))
    if not readiness["ready"] or not args.run:
        sys.stdout.write(json.dumps(dict(readiness=readiness, started=False), ensure_ascii=False, indent=2) + "\n")
        return 2 if not readiness["ready"] else 0
    store = Store(args.data_dir)
    project = store.save_project(project, create=True)
    quote = store.quote(project, dict(kind="generate", project=project, scene=project["scenes"][0],
                                     scene_id=project["scenes"][0]["id"], readiness=readiness,
                                     cost=estimate(project, project["scenes"][0], [])))
    job, _ = store.accept_quote(quote["id"])
    worker = Worker(store, engine)
    peak_mb = None
    try:
        worker.submit(job["id"])
        while True:
            current = store.job(job["id"])
            used = gpu_memory_mb()
            if used is not None:
                peak_mb = max(peak_mb or 0, used)
            if current["state"] not in ("queued", "running"):
                break
            time.sleep(1)
    finally:
        worker.close()
    current["observed_whole_gpu_peak_mb"] = peak_mb
    current["readiness"] = readiness
    current["model_manifest"] = json.loads(args.model_manifest.read_text(encoding="utf-8")) if args.model_manifest else None
    current["output_path"] = str(store.path(current["output_asset_id"])) if current["output_asset_id"] else None
    report = store.directory / f"benchmark-{job['id']}.json"
    report.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stdout.write(json.dumps(dict(state=current["state"], error=current["error"], output_path=current["output_path"],
                                   report=str(report), generation_seconds=current.get("generation_seconds"),
                                   observed_whole_gpu_peak_mb=peak_mb), ensure_ascii=False, indent=2) + "\n")
    return 0 if current["state"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
