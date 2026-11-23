import os
import secrets
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .comfy import ComfyClient
from .example import first_chapter
from .media import normalize_audio, probe
from .models import Project, Record
from .portable import create_request, import_result, request_archive
from .store import Conflict, Store
from .worker import Worker
from .workflows import PRESETS, build_graph, estimate, scene_prompt

WEB = Path(__file__).with_name("web")


class NewProject(Record):
    title: str = Field(min_length=1, max_length=200)


class Accept(Record):
    quote_id: str
    approved: bool


class Apply(Record):
    revision: int


def validate_assets(store, project):
    project_id = project["id"]
    for character in project["characters"]:
        for key, kind in (("reference_asset_id", "image"), ("voice_asset_id", "audio")):
            if character[key]:
                store.path(character[key], project_id, kind)
    for location in project["locations"]:
        if location["reference_asset_id"]:
            store.path(location["reference_asset_id"], project_id, "image")
    for scene in project["scenes"]:
        for key, kind in (("reference_asset_id", "image"), ("video_asset_id", "video"), ("audio_asset_id", "audio")):
            if scene[key]:
                store.path(scene[key], project_id, kind)


def public_quote(quote):
    return {key: value for key, value in quote.items() if key not in ("project", "scene", "voice_request")}


def public_job(job):
    return {key: value for key, value in job.items() if key not in ("payload", "graph")}


def create_app(data_dir=None, engine=None, recover=True):
    directory = Path(data_dir or os.environ.get("RAFIQ_DATA_DIR", Path.home() / "RafiqAIStudio"))
    store = Store(directory)
    comfy = engine or ComfyClient(os.environ.get("RAFIQ_COMFY_URL", "http://127.0.0.1:8188"))
    voice_python = os.environ.get("RAFIQ_VOICE_PYTHON")
    worker = Worker(store, comfy, voice_python)
    session_token = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app):
        if recover:
            store.recover_jobs()
        if not store.list_projects():
            store.save_project(first_chapter(), create=True)
        yield
        worker.close()

    app = FastAPI(title="Rafiq AI Studio", version="0.2.0", lifespan=lifespan)
    app.state.store = store
    app.state.worker = worker
    allowed_hosts = ["localhost", "127.0.0.1", "[::1]", "testserver"]
    allowed_hosts += [host.strip() for host in os.environ.get("RAFIQ_ALLOWED_HOSTS", "").split(",") if host.strip()]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    @app.middleware("http")
    async def local_session(request: Request, call_next):
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > 513 * 1024**2):
            return JSONResponse({"detail": "Request exceeds the MVP size limit"}, status_code=413)
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if request.headers.get("X-Rafiq-Token") != session_token:
                return JSONResponse({"detail": "Reload the studio to establish its local session"}, status_code=403)
            origin = request.headers.get("origin")
            if origin and urlsplit(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "Cross-origin writes are disabled"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.get("/api/bootstrap")
    def bootstrap():
        return dict(token=session_token, version="0.2.0", presets=PRESETS,
                    ffmpeg=bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
                    voice_configured=bool(voice_python and Path(voice_python).is_file()),
                    engine_url=comfy.url, cloud_enabled=False)

    @app.get("/api/projects")
    def projects():
        return store.list_projects()

    @app.post("/api/projects", status_code=201)
    def new_project(body: NewProject):
        return store.save_project(Project(id=uuid.uuid4().hex, title=body.title), create=True)

    @app.post("/api/projects/import", status_code=201)
    def import_project(body: Project):
        project = body.model_dump()
        project.update(id=uuid.uuid4().hex, revision=1)
        for item in project["characters"] + project["locations"] + project["scenes"]:
            for key in list(item):
                if key.endswith("_asset_id"):
                    item[key] = None
        return store.save_project(project, create=True)

    @app.post("/api/projects/example", status_code=201)
    def example():
        return store.save_project(first_chapter(uuid.uuid4().hex), create=True)

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str):
        return store.project(project_id)

    @app.put("/api/projects/{project_id}")
    def save_project(project_id: str, project: Project):
        if project.id != project_id:
            raise ValueError("Project ID cannot change")
        validate_assets(store, project.model_dump())
        return store.save_project(project)

    @app.get("/api/projects/{project_id}/download")
    def download_project(project_id: str):
        return JSONResponse(store.project(project_id), headers={"Content-Disposition": f'attachment; filename="rafiq-project-{project_id}.json"'})

    @app.get("/api/projects/{project_id}/assets")
    def assets(project_id: str):
        store.project(project_id)
        return store.list_assets(project_id)

    @app.post("/api/projects/{project_id}/assets", status_code=201)
    def upload(project_id: str, kind: str, file: UploadFile = File()):
        store.project(project_id)
        limits = {"image": 25 * 1024**2, "audio": 50 * 1024**2, "video": 512 * 1024**2}
        if kind not in limits:
            raise ValueError("Choose image, audio or video")
        temporary = store.assets / f"{uuid.uuid4().hex}.upload"
        target = temporary.with_suffix({"image": ".png", "audio": ".wav", "video": ".mp4"}[kind])
        size = 0
        try:
            with temporary.open("wb") as output:
                while block := file.file.read(1024**2):
                    size += len(block)
                    if size > limits[kind]:
                        raise HTTPException(413, "Upload exceeds the MVP size limit")
                    output.write(block)
            if kind == "image":
                with Image.open(temporary) as image:
                    if image.format not in ("PNG", "JPEG", "WEBP") or image.width * image.height > 32_000_000:
                        raise ValueError("Use a PNG, JPEG or WebP image up to 32 megapixels")
                    image.convert("RGB").save(target, "PNG")
                metadata = dict(width=image.width, height=image.height)
            else:
                metadata = probe(temporary)
                expected = "audio" if kind == "audio" else "video"
                if not any(s["codec_type"] == expected for s in metadata["streams"]):
                    raise ValueError(f"File has no {expected} stream")
                if kind == "audio":
                    normalize_audio(temporary, target)
                else:
                    container = metadata.get("format", {}).get("format_name", "")
                    if "mp4" not in container and "mov" not in container:
                        raise ValueError("Import an MP4 or MOV clip")
                    temporary.replace(target)
                metadata = dict(probe=metadata, provenance="user-import")
            result = store.add_asset(project_id, kind, target, (file.filename or "upload")[:240], metadata)
            return result
        except (UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise ValueError("The image cannot be decoded safely") from exc
        finally:
            temporary.unlink(missing_ok=True)
            file.file.close()

    @app.get("/api/assets/{asset_id}")
    def asset_file(asset_id: str, download: bool = False):
        asset = store.asset(asset_id)
        return FileResponse(store.path(asset_id), filename=asset["filename"] if download else None)

    def find_scene(project, scene_id):
        for scene in project["scenes"]:
            if scene["id"] == scene_id:
                return scene
        raise KeyError("Scene not found")

    @app.post("/api/projects/{project_id}/gpu-request/{scene_id}", status_code=201)
    def export_gpu_request(project_id: str, scene_id: str, body: Apply):
        project = store.project(project_id)
        if project["revision"] != body.revision:
            raise Conflict("Reload the project before exporting this scene")
        job = create_request(store, project, find_scene(project, scene_id))
        return public_job(job)

    @app.get("/api/jobs/{job_id}/gpu-request")
    def download_gpu_request(job_id: str):
        return FileResponse(request_archive(store, store.job(job_id)), filename=f"rafiq-gpu-{job_id}.zip")

    @app.post("/api/projects/{project_id}/gpu-result")
    def import_gpu_result(project_id: str, file: UploadFile = File()):
        store.project(project_id)
        try:
            job, fresh = import_result(store, project_id, file.file)
            return dict(job=public_job(job), imported=fresh)
        finally:
            file.file.close()

    @app.get("/api/gpu-notebook")
    def gpu_notebook():
        path = Path(__file__).parents[1] / "notebooks" / "Rafiq_GPU_Job.ipynb"
        return FileResponse(path, filename=path.name)

    @app.get("/api/projects/{project_id}/readiness/{scene_id}")
    def readiness(project_id: str, scene_id: str):
        project = store.project(project_id)
        scene = find_scene(project, scene_id)
        return comfy.inspect(build_graph(project, scene, reference_name="pending.png"))

    @app.post("/api/projects/{project_id}/estimate/{scene_id}")
    def quote_video(project_id: str, scene_id: str):
        project = store.project(project_id)
        scene = find_scene(project, scene_id)
        if not scene["prompt"].strip():
            raise ValueError("Write a visual scene prompt first")
        validate_assets(store, project)
        if scene["mode"] == "image" and not scene["reference_asset_id"]:
            raise ValueError("Upload and select a scene reference image first")
        graph = build_graph(project, scene, reference_name="pending.png")
        checked = comfy.inspect(graph)
        warnings = ["Character and location descriptions are included in the prompt. They do not guarantee identity consistency.",
                    "Character/location reference sheets are stored for planning. Only the selected scene image conditions this built-in I2V workflow.",
                    "Dialogue is produced separately. This video preset has no generated audio or lip sync."]
        quote = store.quote(project, dict(kind="generate", project=project, scene=scene, scene_id=scene_id,
                            cost=estimate(project, scene, store.jobs(project_id)), readiness=checked,
                            prompt=scene_prompt(project, scene), warnings=warnings))
        return public_quote(quote)

    @app.post("/api/projects/{project_id}/export")
    def quote_export(project_id: str):
        project = store.project(project_id)
        if not project["scenes"] or any(not scene["video_asset_id"] for scene in project["scenes"]):
            raise ValueError("Select a video for every scene before exporting")
        validate_assets(store, project)
        checked = dict(ready=bool(shutil.which("ffmpeg") and shutil.which("ffprobe")), errors=[])
        if not checked["ready"]:
            checked["errors"].append("Install FFmpeg and ffprobe first")
        quote = store.quote(project, dict(kind="export", project=project, readiness=checked,
                            warnings=["Clips and dialogue audio are trimmed to each scene's duration. Short video frames are held until the scene ends."],
                            cost=dict(currency="USD", estimated_seconds=None, estimated_cost=None, source="unknown", provider_fee=0)))
        return public_quote(quote)

    @app.post("/api/projects/{project_id}/voice/{scene_id}")
    def quote_voice(project_id: str, scene_id: str):
        project = store.project(project_id)
        scene = find_scene(project, scene_id)
        if not scene["dialogue"]:
            raise ValueError("Add dialogue lines first")
        characters = {x["id"]: x for x in project["characters"]}
        lines = []
        for line in scene["dialogue"]:
            character = characters[line["character_id"]]
            if not character["voice_asset_id"]:
                raise ValueError(f"Add a voice reference for {character['name']} first")
            lines.append(dict(text=line["text"], language=line["language"], reference=str(store.path(character["voice_asset_id"], project_id, "audio"))))
        configured = bool(voice_python and Path(voice_python).is_file())
        checked = dict(ready=configured, errors=[] if configured else ["Configure RAFIQ_VOICE_PYTHON with cached Chatterbox weights first"])
        quote = store.quote(project, dict(kind="voice", project=project, scene_id=scene_id, readiness=checked,
                            voice_request=dict(seed=scene["seed"], lines=lines), warnings=["Arabic pronunciation and voice similarity require listening review. No lip sync is applied."],
                            cost=dict(currency="USD", estimated_seconds=None, estimated_cost=None, source="unknown", provider_fee=0)))
        return public_quote(quote)

    @app.get("/api/jobs")
    def jobs(project_id: str | None = None):
        return [public_job(job) for job in store.jobs(project_id)]

    @app.get("/api/jobs/{job_id}/manifest")
    def manifest(job_id: str):
        job = store.job(job_id)
        result = {key: value for key, value in job.items() if key != "payload"}
        payload = dict(job["payload"])
        payload.pop("voice_request", None)
        result["payload"] = payload
        return JSONResponse(result, headers={"Content-Disposition": f'attachment; filename="rafiq-job-{job_id}.json"'})

    @app.post("/api/jobs", status_code=202)
    def start_job(body: Accept):
        if not body.approved:
            raise ValueError("Review and approve the estimate before starting")
        job, fresh = store.accept_quote(body.quote_id)
        if fresh:
            if not job["payload"]["readiness"]["ready"]:
                store.update_job(job["id"], state="failed", error="Preflight did not pass. Fix the engine or dependencies and estimate again.")
                raise Conflict("Preflight did not pass")
            worker.submit(job["id"])
        return public_job(job)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str):
        job = store.job(job_id)
        if job["state"] != "queued":
            raise Conflict("Only waiting jobs can be cancelled here. Check ComfyUI for an active prompt.")
        return public_job(store.transition_job(job_id, "queued", state="cancelled"))

    @app.post("/api/jobs/{job_id}/apply")
    def use_result(job_id: str, body: Apply):
        job = store.job(job_id)
        if job["state"] != "succeeded" or job["kind"] == "export":
            raise Conflict("No scene output is available")
        project = store.project(job["project_id"])
        if project["revision"] != body.revision:
            raise Conflict("Reload the latest project before attaching this result")
        scene = find_scene(project, job["scene_id"])
        scene["audio_asset_id" if job["kind"] == "voice" else "video_asset_id"] = job["output_asset_id"]
        return store.save_project(project)

    app.mount("/static", StaticFiles(directory=WEB), name="static")

    @app.get("/")
    def index():
        return FileResponse(WEB / "index.html")

    return app
