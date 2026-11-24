import argparse

import uvicorn

from .app import create_app


def main():
    parser = argparse.ArgumentParser(description="Start Rafiq AI Studio on your local computer")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--data-dir")
    parser.add_argument("--strictPort", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    # Uvicorn always fails on an occupied port, matching the preview launcher's --strictPort.
    uvicorn.run(create_app(args.data_dir), host=args.host, port=args.port, access_log=False)


if __name__ == "__main__":
    main()
