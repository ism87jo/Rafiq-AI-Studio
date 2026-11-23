"""Boot ComfyUI on CPU and encode a diagnostic MP4 without model weights."""
import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import av

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rafiq.studio.comfy import ComfyClient
from rafiq.studio.example import first_chapter
from rafiq.studio.workflows import build_graph


def verify_native_video(url, directory):
    project = first_chapter().model_dump()
    graph = build_graph(project, project["scenes"][0], prefix="native-video-smoke")
    graph = {
        "9": {"class_type": "EmptyImage", "inputs": {"width": 64, "height": 64, "batch_size": 1, "color": 0x245432}},
        "10": graph["10"],
        "11": graph["11"],
    }
    client = ComfyClient(url, timeout_seconds=60)
    output = client.generate(graph, Path(directory) / "native-video.mp4", lambda prompt_id: None)
    with av.open(str(output)) as video:
        stream = video.streams.video[0]
        if stream.codec_context.name != "h264" or (stream.width, stream.height) != (64, 64):
            raise RuntimeError("Native SaveVideo returned an unexpected codec or dimensions")
        if next(video.decode(video=0), None) is None:
            raise RuntimeError("Native SaveVideo returned no decodable frames")
    sys.stdout.write("Native ComfyUI CreateVideo/SaveVideo H.264 test passed (diagnostic frame, not AI inference).\n")


def main():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    with tempfile.TemporaryDirectory(dir=ROOT / "rafiq") as directory:
        log_path = Path(directory) / "server.log"
        with log_path.open("wb") as log:
            server = subprocess.Popen(
                [
                    sys.executable, "main.py", "--cpu", "--offline",
                    "--listen", "127.0.0.1", "--port", str(port),
                    "--disable-auto-launch", "--disable-all-custom-nodes",
                    "--user-directory", directory,
                    "--output-directory", str(Path(directory) / "output"),
                ],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline and server.poll() is None:
                    try:
                        with urlopen(f"http://127.0.0.1:{port}/system_stats", timeout=2) as response:
                            stats = json.load(response)
                    except (URLError, TimeoutError):
                        time.sleep(1)
                        continue
                    if not stats.get("system") or not any(
                        device["type"] == "cpu" for device in stats["devices"]
                    ):
                        raise RuntimeError(f"Unexpected system_stats response: {stats}")
                    verify_native_video(f"http://127.0.0.1:{port}", directory)
                    sys.stdout.write("ComfyUI CPU smoke test passed.\n")
                    return
                raise RuntimeError(f"ComfyUI did not become ready (exit status {server.poll()}).")
            except Exception:
                sys.stderr.write(log_path.read_text(encoding="utf-8", errors="replace"))
                raise
            finally:
                if server.poll() is None:
                    server.terminate()
                    server.wait(timeout=10)


if __name__ == "__main__":
    main()
