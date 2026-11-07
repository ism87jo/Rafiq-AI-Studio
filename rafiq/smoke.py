"""Boot ComfyUI in CPU mode and verify its HTTP API without model weights."""
import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


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
                    print("ComfyUI CPU smoke test passed.")
                    return
                raise RuntimeError(f"ComfyUI did not become ready (exit status {server.poll()}).")
            except Exception:
                print(log_path.read_text(encoding="utf-8", errors="replace"), file=sys.stderr)
                raise
            finally:
                if server.poll() is None:
                    server.terminate()
                    server.wait(timeout=10)


if __name__ == "__main__":
    main()
