"""Move one shot to an owned GPU using bounded request/result ZIP files."""
import argparse
import copy
import hashlib
import json
import shutil
import stat
import sys
import uuid
import zipfile
from pathlib import Path
from typing import Literal

from PIL import Image, UnidentifiedImageError
from pydantic import Field, model_validator

from .comfy import ComfyClient
from .media import probe
from .models import Project, Record
from .store import Conflict, Store
from .worker import Worker
from .workflows import build_graph

MIB = 1024**2
META_LIMIT = 2 * MIB
IMAGE_LIMIT = 25 * MIB
VIDEO_LIMIT = 500 * MIB


class GPURequest(Record):
    version: Literal[1]
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    project: Project
    reference_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def one_shot(self):
        if len(self.project.scenes) != 1:
            raise ValueError("A GPU request must contain exactly one scene")
        if (self.project.scenes[0].mode == "image") != bool(self.reference_sha256):
            raise ValueError("Image-to-video requires a hashed scene reference")
        return self


class GPUResult(Record):
    version: Literal[1]
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    request_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    video_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)
    generation_seconds: float = Field(ge=0, allow_inf_nan=False)
    devices: list[dict] = Field(default_factory=list, max_length=16)
    model_manifest: dict | None = None
    source_commit: str | None = Field(default=None, pattern=r"^[a-f0-9]{40}$")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked_archive(source, names):
    try:
        archive = zipfile.ZipFile(source)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("Use a valid Rafiq GPU ZIP file") from exc
    try:
        entries = archive.infolist()
        if len(entries) != len({item.filename for item in entries}):
            raise ValueError("Duplicate ZIP members are not allowed")
        if sum(item.file_size for item in entries) > 512 * MIB:
            raise ValueError("GPU ZIP exceeds the unpacked size limit")
        for item in entries:
            if item.filename not in names or stat.S_ISLNK(item.external_attr >> 16) or item.flag_bits & 1:
                raise ValueError("Unexpected, linked or encrypted ZIP member")
            if item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise ValueError("Unsupported ZIP compression")
            if item.file_size > names[item.filename]:
                raise ValueError(f"ZIP member is too large: {item.filename}")
    except ValueError:
        archive.close()
        raise
    return archive


def member_bytes(archive, name, limit):
    try:
        info = archive.getinfo(name)
    except KeyError as exc:
        raise ValueError(f"Missing ZIP member: {name}") from exc
    if info.file_size > limit:
        raise ValueError(f"ZIP member is too large: {name}")
    with archive.open(info) as stream:
        content = stream.read(limit + 1)
    if len(content) > limit:
        raise ValueError(f"ZIP member is too large: {name}")
    return content


def load_request(archive):
    request = GPURequest.model_validate_json(member_bytes(archive, "request.json", META_LIMIT)).model_dump()
    build_graph(request["project"], request["project"]["scenes"][0], reference_name="reference.png")
    return request


def create_request(store, project, scene):
    if not scene["prompt"].strip():
        raise ValueError("Write a visual scene prompt first")
    build_graph(project, scene, reference_name="reference.png")
    reference = None
    if scene["mode"] == "image":
        if not scene["reference_asset_id"]:
            raise ValueError("Select the scene reference image before exporting")
        reference = store.path(scene["reference_asset_id"], project["id"], "image")
    snapshot = copy.deepcopy(project)
    snapshot["script"] = ""
    snapshot["scenes"] = [copy.deepcopy(scene)]
    snapshot["scenes"][0].update(dialogue=[], notes="", reference_asset_id=None, video_asset_id=None, audio_asset_id=None)
    snapshot["characters"] = [item for item in snapshot["characters"] if item["id"] in scene["character_ids"]]
    snapshot["locations"] = [item for item in snapshot["locations"] if item["id"] == scene["location_id"]]
    for character in snapshot["characters"]:
        character.update(reference_asset_id=None, voice_asset_id=None, voice_notes="")
    for location in snapshot["locations"]:
        location["reference_asset_id"] = None
    for key in ("electricity_usd_kwh", "system_watts", "assumed_render_seconds"):
        snapshot["settings"][key] = None
    request = GPURequest(version=1, id=uuid.uuid4().hex, project=Project.model_validate(snapshot),
                         reference_sha256=digest_file(reference) if reference else None).model_dump()
    request_digest = hashlib.sha256(canonical(request)).hexdigest()
    return store.create_portable_job(project, scene, request, request_digest, scene["reference_asset_id"] if reference else None)


def request_archive(store, job):
    if job.get("execution") != "portable":
        raise ValueError("This is not a portable GPU job")
    directory = store.directory / "gpu-requests"
    directory.mkdir(exist_ok=True)
    path = directory / f"{job['id']}.zip"
    if path.is_file():
        return path
    request = job["payload"]["request"]
    reference = None
    if request["reference_sha256"]:
        reference = store.path(job["payload"]["reference_asset_id"], job["project_id"], "image")
        if digest_file(reference) != request["reference_sha256"]:
            raise Conflict("The exported reference image has changed")
    temporary = directory / f"{uuid.uuid4().hex}.tmp"
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("request.json", canonical(request))
            if reference:
                archive.write(reference, "reference.png")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def inspect_request(source):
    with checked_archive(source, {"request.json": META_LIMIT, "reference.png": IMAGE_LIMIT}) as archive:
        request = load_request(archive)
        if request["reference_sha256"]:
            content = member_bytes(archive, "reference.png", IMAGE_LIMIT)
            if hashlib.sha256(content).hexdigest() != request["reference_sha256"]:
                raise ValueError("Reference image checksum mismatch")
        return request


def render_request(source, output, engine=None, model_manifest=None, source_commit=None):
    request = inspect_request(source)
    engine = engine or ComfyClient(timeout_seconds=1800)
    project = copy.deepcopy(request["project"])
    scene = project["scenes"][0]
    request_digest = hashlib.sha256(canonical(request)).hexdigest()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("The result path already exists; choose a new path")
    output.parent.mkdir(parents=True, exist_ok=True)
    store = Store(output.parent / f"rafiq-gpu-work-{request['id']}")
    previous = store.jobs()
    if previous:
        completed = previous[0]
        if completed["payload"].get("source_request_digest") != request_digest:
            raise Conflict("This GPU work folder belongs to another request")
        if completed["state"] != "succeeded":
            raise Conflict(f"GPU job already recorded as {completed['state']} (prompt {completed.get('prompt_id')}). Check ComfyUI history before retrying; no new prompt was submitted.")
    else:
        checked = engine.inspect(build_graph(project, scene, reference_name="reference.png"))
        if not checked["ready"]:
            raise ValueError("\n".join(checked["errors"]))
        if request["reference_sha256"]:
            with checked_archive(source, {"request.json": META_LIMIT, "reference.png": IMAGE_LIMIT}) as archive:
                reference = store.assets / f"{uuid.uuid4().hex}.png"
                reference.write_bytes(member_bytes(archive, "reference.png", IMAGE_LIMIT))
            try:
                with Image.open(reference) as image:
                    if image.format != "PNG" or image.width * image.height > 32_000_000:
                        raise ValueError("Use a PNG scene reference up to 32 megapixels")
                    image.verify()
            except (UnidentifiedImageError, Image.DecompressionBombError) as exc:
                raise ValueError("Invalid scene reference image") from exc
            asset = store.add_asset(project["id"], "image", reference, "reference.png")
            scene["reference_asset_id"] = asset["id"]
        project = store.save_project(Project.model_validate(project), create=True)
        quote = store.quote(project, dict(kind="generate", project=project, scene=project["scenes"][0],
                                         scene_id=scene["id"], readiness=checked, source_request_digest=request_digest,
                                         model_manifest=model_manifest, source_commit=source_commit))
        job, _ = store.accept_quote(quote["id"])
        worker = Worker(store, engine)
        try:
            worker.run(job["id"])
        finally:
            worker.close()
        completed = store.job(job["id"])
        if completed["state"] != "succeeded":
            raise ValueError(completed["error"] or "GPU generation failed")
    video = store.path(completed["output_asset_id"])
    if video.suffix != ".mp4" or video.stat().st_size > VIDEO_LIMIT:
        raise ValueError("The portable result requires an MP4 up to 500 MiB")
    result = GPUResult(version=1, request_id=request["id"], request_sha256=request_digest, video_sha256=digest_file(video),
                       elapsed_seconds=completed["elapsed_seconds"], generation_seconds=completed["generation_seconds"],
                       devices=completed["payload"]["readiness"]["devices"],
                       model_manifest=completed["payload"]["model_manifest"], source_commit=completed["payload"]["source_commit"]).model_dump()
    temporary = output.with_name(f"{uuid.uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("request.json", canonical(request))
            archive.writestr("result.json", canonical(result))
            archive.write(video, "clip.mp4")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return result


def import_result(store, project_id, source):
    target = store.assets / f"{uuid.uuid4().hex}.mp4"
    retained = False
    try:
        with checked_archive(source, {"request.json": META_LIMIT, "result.json": META_LIMIT, "clip.mp4": VIDEO_LIMIT}) as archive:
            request = load_request(archive)
            result = GPUResult.model_validate_json(member_bytes(archive, "result.json", META_LIMIT)).model_dump()
            request_digest = hashlib.sha256(canonical(request)).hexdigest()
            if result["request_id"] != request["id"] or result["request_sha256"] != request_digest:
                raise ValueError("Result/request checksum mismatch")
            job = store.job(request["id"])
            if job["project_id"] != project_id:
                raise KeyError("GPU job not found in this project")
            if job.get("execution") != "portable" or job["payload"]["request_digest"] != request_digest:
                raise Conflict("The result belongs to a different exported request")
            try:
                info = archive.getinfo("clip.mp4")
            except KeyError as exc:
                raise ValueError("Missing video in GPU result") from exc
            with archive.open(info) as incoming, target.open("wb") as outgoing:
                shutil.copyfileobj(incoming, outgoing, length=MIB)
        if digest_file(target) != result["video_sha256"]:
            raise ValueError("Video checksum mismatch")
        metadata = probe(target)
        if not any(stream["codec_type"] == "video" for stream in metadata["streams"]) or "mp4" not in metadata["format"]["format_name"]:
            raise ValueError("The GPU result does not contain an MP4 video")
        asset = dict(id=target.stem, filename=target.name, original_name=f"gpu-{request['id']}.mp4",
                     metadata=dict(provenance="portable-comfyui", request_digest=request_digest, probe=metadata))
        job, retained = store.complete_portable_job(request["id"], project_id, request_digest, result, asset)
        return job, retained
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise ValueError("The GPU ZIP is damaged or cannot be read") from exc
    finally:
        if not retained:
            target.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--model-manifest", type=Path)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    if not args.run:
        request = inspect_request(args.request)
        project = request["project"]
        sys.stdout.write(json.dumps(dict(id=request["id"], preset=project["settings"]["preset"], scene=project["scenes"][0]["title"]), ensure_ascii=False) + "\n")
        return
    if not args.output:
        parser.error("--output is required with --run")
    manifest = json.loads(args.model_manifest.read_text(encoding="utf-8")) if args.model_manifest else None
    result = render_request(args.request, args.output, model_manifest=manifest, source_commit=args.source_commit)
    sys.stdout.write(json.dumps(dict(output=str(args.output), result=result), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
