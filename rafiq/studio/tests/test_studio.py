import json
import shutil
import subprocess
import tempfile
import time
import unittest
import wave
from io import BytesIO
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from PIL import Image

from rafiq.studio.app import create_app
from rafiq.studio.comfy import ComfyClient
from rafiq.studio.example import first_chapter
from rafiq.studio.media import probe
from rafiq.studio.store import Conflict, Store
from rafiq.studio.workflows import PRESETS, build_graph, frame_count


class EngineFixture:
    """Protocol fixture, not neural inference. Output is a real FFmpeg test clip."""

    def __init__(self, video):
        self.video = video
        self.graphs = []
        self.uploads = []
        self.missing = False
        self.cpu = False
        self.api_node = False
        self.fail = False
        self.no_output = False

    def respond(self, request):
        path = request.url.path
        if path == "/system_stats":
            return httpx.Response(200, json={"devices": [{"type": "cpu" if self.cpu else "cuda", "name": "TEST FIXTURE — NOT A REAL GPU"}]})
        if path == "/object_info":
            graph = build_graph(first_chapter().model_dump(), first_chapter().model_dump()["scenes"][0])
            result = {node["class_type"]: {"input": {"required": {}}} for node in graph.values()}
            result["LoadImage"] = {"input": {"required": {}}}
            for name, field, value in (("UNETLoader", "unet_name", PRESETS["wan22-5b"]["model"]),
                                       ("CLIPLoader", "clip_name", PRESETS["wan22-5b"]["encoder"]),
                                       ("VAELoader", "vae_name", PRESETS["wan22-5b"]["vae"])):
                result[name]["input"]["required"][field] = [[value] if not self.missing else [], {}]
            result["KSampler"]["api_node"] = self.api_node
            return httpx.Response(200, json=result)
        if path == "/upload/image":
            self.uploads.append(request.content)
            return httpx.Response(200, json={"name": "reference.png", "subfolder": "rafiq"})
        if path == "/prompt":
            self.graphs.append(json.loads(request.content)["prompt"])
            return httpx.Response(200, json={"prompt_id": f"test-{len(self.graphs)}"})
        if path.startswith("/history/"):
            prompt_id = path.rsplit("/", 1)[-1]
            result = {"status": {"completed": True, "status_str": "error" if self.fail else "success"},
                      "outputs": {} if self.no_output else {"11": {"images": [{"filename": "test.mp4", "type": "output", "subfolder": "rafiq"}]}}}
            return httpx.Response(200, json={prompt_id: result})
        if path == "/view":
            return httpx.Response(200, content=self.video, headers={"content-type": "video/mp4"})
        return httpx.Response(404)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "Requires real FFmpeg")
class StudioIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media_dir = tempfile.TemporaryDirectory()
        path = Path(cls.media_dir.name) / "fixture.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=0x245432:s=160x96:r=8:d=0.5", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
        cls.video = path.read_bytes()
        audio = BytesIO()
        with wave.open(audio, "wb") as wav:
            wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            wav.writeframes(b"\x00\x00" * 12000)
        cls.audio = audio.getvalue()

    @classmethod
    def tearDownClass(cls):
        cls.media_dir.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.fixture = EngineFixture(self.video)
        self.engine = ComfyClient(transport=httpx.MockTransport(self.fixture.respond))
        self.app = create_app(self.directory.name, self.engine)
        self.context = TestClient(self.app)
        self.client = self.context.__enter__()
        self.headers = {"X-Rafiq-Token": self.client.get("/api/bootstrap").json()["token"]}
        self.project = self.client.get("/api/projects").json()[0]
        self.pid = self.project["id"]
        self.sid = self.project["scenes"][0]["id"]

    def tearDown(self):
        self.context.__exit__(None, None, None)
        self.directory.cleanup()

    def post(self, url, **kwargs):
        return self.client.post(url, headers=self.headers, **kwargs)

    def save(self):
        response = self.client.put(f"/api/projects/{self.pid}", headers=self.headers, json=self.project)
        self.assertEqual(response.status_code, 200, response.text)
        self.project = response.json()

    def quote(self):
        response = self.post(f"/api/projects/{self.pid}/estimate/{self.sid}")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def accept(self, quote):
        response = self.post("/api/jobs", json={"quote_id": quote["id"], "approved": True})
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()

    def wait_job(self, job):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            result = self.app.state.store.job(job["id"])
            if result["state"] not in ("queued", "running"):
                return result
            time.sleep(0.05)
        self.fail("Job did not finish")

    def upload(self, kind, content, filename, content_type):
        response = self.post(f"/api/projects/{self.pid}/assets?kind={kind}", files={"file": (filename, content, content_type)})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_initial_project_and_session_protection(self):
        self.assertEqual(len(self.project["characters"]), 4)
        self.assertEqual(len(self.project["scenes"]), 6)
        self.assertIn("الطائر", self.project["title"])
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/static/studio.js").status_code, 200)
        self.assertEqual(self.client.post("/api/projects", json={"title": "bad"}).status_code, 403)
        response = self.client.post("/api/projects", headers={**self.headers, "Origin": "https://untrusted.example"}, json={"title": "bad"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/api/projects", headers={"Host": "attacker.example"}).status_code, 400)
        self.assertFalse(self.client.get("/api/bootstrap").json()["cloud_enabled"])

    def test_optimistic_revision_prevents_lost_updates(self):
        old = dict(self.project)
        self.project["title"] = "حفظ جديد"
        self.save()
        response = self.client.put(f"/api/projects/{self.pid}", headers=self.headers, json=old)
        self.assertEqual(response.status_code, 409)

    def test_unknown_cost_is_not_zero_and_estimate_uses_explicit_inputs(self):
        quote = self.quote()
        self.assertIsNone(quote["cost"]["estimated_cost"])
        self.assertEqual(quote["cost"]["source"], "unknown")
        self.project["settings"].update(assumed_render_seconds=180, system_watts=400, electricity_usd_kwh=0.2)
        self.save()
        quote = self.quote()
        self.assertAlmostEqual(quote["cost"]["estimated_cost"], 0.004)
        self.assertEqual(quote["cost"]["source"], "user-assumption")

    def test_stale_quote_and_missing_approval_are_rejected(self):
        quote = self.quote()
        response = self.post("/api/jobs", json={"quote_id": quote["id"], "approved": False})
        self.assertEqual(response.status_code, 422)
        self.project["scenes"][0]["prompt"] += " Changed framing."
        self.save()
        response = self.post("/api/jobs", json={"quote_id": quote["id"], "approved": True})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(len(self.fixture.graphs), 0)

    def test_expired_quote_never_submits(self):
        quote = self.quote()
        with self.app.state.store.connect() as db:
            db.execute("UPDATE quotes SET expires=? WHERE id=?", (time.time() - 1, quote["id"]))
        response = self.post("/api/jobs", json={"quote_id": quote["id"], "approved": True})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.fixture.graphs, [])

    def test_preflight_blocks_missing_weights_cpu_and_paid_nodes(self):
        for attribute in ("missing", "cpu", "api_node"):
            with self.subTest(attribute=attribute):
                setattr(self.fixture, attribute, True)
                quote = self.quote()
                self.assertFalse(quote["readiness"]["ready"])
                response = self.post("/api/jobs", json={"quote_id": quote["id"], "approved": True})
                self.assertEqual(response.status_code, 409)
                setattr(self.fixture, attribute, False)
        self.assertEqual(self.fixture.graphs, [])

    def test_protocol_roundtrip_real_mp4_and_idempotent_submission(self):
        quote = self.quote()
        self.assertTrue(quote["readiness"]["ready"])
        job = self.accept(quote)
        repeated = self.accept(quote)
        self.assertEqual(job["id"], repeated["id"])
        result = self.wait_job(job)
        self.assertEqual(result["state"], "succeeded", result["error"])
        self.assertEqual(len(self.fixture.graphs), 1)
        graph = self.fixture.graphs[0]
        self.assertIn("Olive green", graph["4"]["inputs"]["text"])
        self.assertIn("Jordanian stone courtyard", graph["4"]["inputs"]["text"])
        self.assertEqual(graph["8"]["inputs"]["seed"], 41201)
        self.assertEqual(self.client.get(f"/api/assets/{result['output_asset_id']}").content, self.video)
        manifest = self.client.get(f"/api/jobs/{job['id']}/manifest").json()
        self.assertEqual(manifest["graph"]["8"]["inputs"]["seed"], 41201)
        response = self.post(f"/api/jobs/{job['id']}/apply", json={"revision": self.project["revision"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["scenes"][0]["video_asset_id"], result["output_asset_id"])
        self.assertEqual(self.quote()["cost"]["source"], "measured-similar-jobs")

    def test_image_to_video_upload_is_actually_bound_to_graph(self):
        image = BytesIO()
        Image.new("RGB", (128, 96), "green").save(image, format="PNG")
        asset = self.upload("image", image.getvalue(), "../../outside.png", "image/png")
        self.assertNotIn("..", asset["filename"])
        self.project["scenes"][0].update(mode="image", reference_asset_id=asset["id"])
        self.save()
        result = self.wait_job(self.accept(self.quote()))
        self.assertEqual(result["state"], "succeeded", result["error"])
        self.assertEqual(len(self.fixture.uploads), 1)
        graph = self.fixture.graphs[0]
        self.assertEqual(graph["12"]["inputs"]["image"], "rafiq/reference.png")
        self.assertEqual(graph["6"]["inputs"]["start_image"], ["12", 0])

    def test_engine_error_never_becomes_a_fake_success(self):
        for flag in ("fail", "no_output"):
            with self.subTest(flag=flag):
                setattr(self.fixture, flag, True)
                result = self.wait_job(self.accept(self.quote()))
                self.assertEqual(result["state"], "failed")
                self.assertIsNone(result["output_asset_id"])
                setattr(self.fixture, flag, False)

    def test_real_ffmpeg_export_import_audio_hold_frames_and_restart(self):
        video = self.upload("video", self.video, "clip.mp4", "video/mp4")
        audio = self.upload("audio", self.audio, "dialogue.wav", "audio/wav")
        self.project["scenes"] = self.project["scenes"][:2]
        self.project["settings"].update(width=160, height=96, fps=8)
        for shot in self.project["scenes"]:
            shot.update(video_asset_id=video["id"], seconds=1)
        self.project["scenes"][0]["audio_asset_id"] = audio["id"]
        self.save()
        quote = self.post(f"/api/projects/{self.pid}/export").json()
        result = self.wait_job(self.accept(quote))
        self.assertEqual(result["state"], "succeeded", result["error"])
        file = self.app.state.store.path(result["output_asset_id"])
        metadata = probe(file)
        self.assertTrue(any(stream["codec_name"] == "h264" for stream in metadata["streams"]))
        self.assertTrue(any(stream["codec_name"] == "aac" for stream in metadata["streams"]))
        self.assertGreaterEqual(float(metadata["format"]["duration"]), 2)
        self.assertEqual(Store(Path(self.directory.name)).project(self.pid)["scenes"][0]["video_asset_id"], video["id"])

    def test_cross_project_assets_and_invalid_uploads_are_rejected(self):
        other = self.post("/api/projects", json={"title": "Other"}).json()
        video = self.upload("video", self.video, "clip.mp4", "video/mp4")
        other["scenes"] = self.project["scenes"][:1]
        other["characters"] = self.project["characters"]
        other["locations"] = self.project["locations"]
        other["scenes"][0]["video_asset_id"] = video["id"]
        response = self.client.put(f"/api/projects/{other['id']}", headers=self.headers, json=other)
        self.assertEqual(response.status_code, 404)
        response = self.post(f"/api/projects/{self.pid}/assets?kind=image", files={"file": ("bad.png", b"not a picture", "image/png")})
        self.assertEqual(response.status_code, 422)

    def test_import_json_creates_copy_without_stale_media_links(self):
        self.project["scenes"][0]["video_asset_id"] = "nonexistent"
        response = self.post("/api/projects/import", json=self.project)
        self.assertEqual(response.status_code, 201)
        copy = response.json()
        self.assertNotEqual(copy["id"], self.pid)
        self.assertIsNone(copy["scenes"][0]["video_asset_id"])

    def test_voice_reference_is_required(self):
        sid = self.project["scenes"][2]["id"]
        response = self.post(f"/api/projects/{self.pid}/voice/{sid}")
        self.assertEqual(response.status_code, 422)
        self.assertIn("voice reference", response.json()["detail"])


class StoreAndWorkflowTests(unittest.TestCase):
    def test_frame_alignment_and_reference_contract(self):
        self.assertEqual((frame_count(5, 24) - 1) % 4, 0)
        project = first_chapter().model_dump()
        scene = project["scenes"][0]
        scene["mode"] = "image"
        with self.assertRaises(ValueError):
            build_graph(project, scene)
        project["settings"]["preset"] = "wan21-1.3b"
        with self.assertRaises(ValueError):
            build_graph(project, scene, "image.png")

    def test_remote_endpoints_are_disabled(self):
        for url in ("https://paid.example", "http://192.168.1.5:8188", "http://localhost:8188/path", "http://user:pass@127.0.0.1:8188"):
            with self.assertRaises(ValueError):
                ComfyClient(url)

    def test_recovery_and_cancel_claim_are_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            project = store.save_project(first_chapter(), create=True)
            quote = store.quote(project, {"kind": "generate", "scene_id": "shot-01"})
            job, fresh = store.accept_quote(quote["id"])
            self.assertTrue(fresh)
            store.transition_job(job["id"], "queued", state="cancelled")
            with self.assertRaises(Conflict):
                store.transition_job(job["id"], "queued", state="running")
            other, _ = store.accept_quote(store.quote(project, {"kind": "generate"})["id"])
            store.update_job(other["id"], state="running", prompt_id="already-submitted")
            store.recover_jobs()
            self.assertEqual(store.job(other["id"])["state"], "interrupted")
            self.assertEqual(store.job(other["id"])["prompt_id"], "already-submitted")


if __name__ == "__main__":
    unittest.main()
