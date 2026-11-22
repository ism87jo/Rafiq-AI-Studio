import ipaddress
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx


class EngineError(ValueError):
    pass


class ComfyClient:
    def __init__(self, url="http://127.0.0.1:8188", transport=None, timeout_seconds=3600):
        parsed = urlsplit(url)
        try:
            local = parsed.hostname == "localhost" or ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            local = False
        if parsed.scheme != "http" or not local or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise ValueError("MVP requires a loopback ComfyUI URL such as http://127.0.0.1:8188")
        self.url = url.rstrip("/")
        self.transport = transport
        self.timeout_seconds = timeout_seconds

    def client(self, timeout=10):
        return httpx.Client(base_url=self.url, timeout=timeout, transport=self.transport,
                            trust_env=False, follow_redirects=False)

    def inspect(self, graph):
        errors = []
        devices = []
        try:
            with self.client(3) as client:
                response = client.get("/system_stats")
                response.raise_for_status()
                devices = response.json().get("devices", [])
                response = client.get("/object_info")
                response.raise_for_status()
                definitions = response.json()
            if not any(device.get("type") in ("cuda", "mps", "xpu", "privateuseone", "npu") for device in devices):
                errors.append("No supported accelerator reported by ComfyUI. CPU video generation is not enabled in this MVP.")
            for item in graph.values():
                name = item["class_type"]
                if name not in definitions:
                    errors.append(f"Missing ComfyUI node: {name}")
                    continue
                definition = definitions[name]
                if definition.get("api_node"):
                    errors.append(f"Paid/API node is disabled: {name}")
                for field in ("unet_name", "clip_name", "vae_name"):
                    value = item["inputs"].get(field)
                    if value is None:
                        continue
                    schema = definition.get("input", {}).get("required", {}).get(field)
                    if schema and isinstance(schema[0], list) and value not in schema[0]:
                        errors.append(f"Missing model file: {value}")
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(f"ComfyUI unavailable at {self.url}: {exc}")
        return dict(ready=not errors, errors=errors, devices=devices, endpoint=self.url,
                    billing="local-only", gpu_generation_verified=False)

    def upload_image(self, path):
        with self.client(60) as client, path.open("rb") as source:
            response = client.post("/upload/image", files={"image": (path.name, source, "image/png")},
                                   data={"type": "input", "subfolder": "rafiq", "overwrite": "false"})
            response.raise_for_status()
            result = response.json()
        return "/".join(x for x in (result.get("subfolder"), result["name"]) if x)

    def generate(self, graph, destination, on_submit, stop_event=None):
        with self.client(30) as client:
            response = client.post("/prompt", json={"prompt": graph, "client_id": destination.stem})
            response.raise_for_status()
            result = response.json()
            if result.get("error") or result.get("node_errors"):
                raise EngineError(f"ComfyUI rejected the workflow: {result}")
            prompt_id = result["prompt_id"]
            on_submit(prompt_id)
            deadline = time.monotonic() + self.timeout_seconds
            while time.monotonic() < deadline:
                if stop_event is not None and stop_event.is_set():
                    raise EngineError("Studio monitoring stopped. The prompt may still be running in ComfyUI; check its history before retrying.")
                response = client.get(f"/history/{prompt_id}")
                response.raise_for_status()
                history = response.json().get(prompt_id)
                if history:
                    status = history.get("status", {})
                    if status.get("status_str") == "error":
                        raise EngineError(f"ComfyUI execution failed: {status.get('messages', [])}")
                    if status.get("completed"):
                        return self.download_output(client, history, destination)
                time.sleep(1)
        raise EngineError("Generation timed out. It may still be running in ComfyUI; check its history before retrying.")

    def download_output(self, client, history, destination):
        output = history.get("outputs", {}).get("11", {})
        media = [item for key in ("images", "videos", "gifs") for item in output.get(key, [])
                 if Path(item.get("filename", "")).suffix.lower() in (".mp4", ".webm", ".mkv", ".mov")]
        if not media:
            raise EngineError("The workflow completed without a video output from SaveVideo.")
        item = media[0]
        destination = destination.with_suffix(Path(item["filename"]).suffix.lower())
        size = 0
        try:
            with client.stream("GET", "/view", params={key: item[key] for key in ("filename", "subfolder", "type") if key in item}) as response:
                response.raise_for_status()
                with destination.open("wb") as target:
                    for block in response.iter_bytes():
                        size += len(block)
                        if size > 2 * 1024**3:
                            raise EngineError("Video exceeds the 2 GiB MVP download limit")
                        target.write(block)
        except (httpx.HTTPError, EngineError):
            destination.unlink(missing_ok=True)
            raise
        return destination
