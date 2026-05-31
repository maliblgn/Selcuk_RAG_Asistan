"""Upload/runtime diagnostics for Streamlit deployments."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


SAFE_ENV_KEYS = ("SPACE_ID", "SPACE_HOST", "PORT")
STREAMLIT_OPTIONS = (
    "server.enableCORS",
    "server.enableXsrfProtection",
    "server.maxUploadSize",
    "server.maxMessageSize",
    "server.port",
    "server.address",
)
SECRET_MARKERS = ("token", "secret", "key", "password", "hf_")


def _is_secretish(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(marker in lowered for marker in SECRET_MARKERS)


def read_safe_streamlit_config(path: str | Path = ".streamlit/config.toml") -> str:
    config_path = Path(path)
    if not config_path.exists():
        return ""
    lines = []
    for line in config_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if _is_secretish(line):
            lines.append("<redacted>")
        else:
            lines.append(line)
    return "\n".join(lines)


def collect_upload_diagnostics(st_module: Any | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "cwd": os.getcwd(),
        "env": {key: os.environ.get(key, "") for key in SAFE_ENV_KEYS},
        "config_exists": Path(".streamlit/config.toml").exists(),
        "config_toml": read_safe_streamlit_config(),
    }
    if st_module is not None:
        data["streamlit_version"] = getattr(st_module, "__version__", "")
        options = {}
        for option in STREAMLIT_OPTIONS:
            try:
                value = st_module.get_option(option)
            except Exception as exc:
                value = f"<unavailable: {type(exc).__name__}>"
            options[option] = value
        data["streamlit_options"] = options
    return data


def diagnostics_are_secret_safe(diagnostics: dict[str, Any]) -> bool:
    rendered = repr(diagnostics).lower()
    return not any(marker in rendered for marker in ("hf_token", "api_key", "groq_api_key", "password="))
