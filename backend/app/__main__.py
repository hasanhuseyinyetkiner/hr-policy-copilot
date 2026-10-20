"""Run the API on the configured loopback address."""

import sys

import uvicorn

from app.config import enforce_loopback, get_settings


def main() -> None:
    settings = get_settings()
    try:
        enforce_loopback(settings)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
