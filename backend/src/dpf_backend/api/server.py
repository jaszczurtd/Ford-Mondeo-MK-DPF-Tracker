"""Command-line entry point for the DPF backend HTTP API."""

from __future__ import annotations

import argparse

from dpf_backend.config import load_settings


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the DPF backend API server.")
    parser.add_argument("--host", help="Bind host. Defaults to DPF_API_HOST.")
    parser.add_argument("--port", type=int, help="Bind port. Defaults to DPF_API_PORT.")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn reload for local development.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    settings = load_settings()
    host = args.host or settings.api_host
    port = args.port or settings.api_port

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - depends on deployment env
        raise RuntimeError("uvicorn is not installed") from exc

    uvicorn.run(
        "dpf_backend.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
