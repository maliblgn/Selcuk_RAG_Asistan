from pathlib import Path

from session_sources.upload_diagnostics import (
    collect_upload_diagnostics,
    diagnostics_are_secret_safe,
    read_safe_streamlit_config,
)


def test_read_safe_streamlit_config_redacts_secret_lines(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        """
        [server]
        maxUploadSize = 25
        hf_token = "secret"
        """,
        encoding="utf-8",
    )

    safe = read_safe_streamlit_config(config)

    assert "maxUploadSize" in safe
    assert "secret" not in safe
    assert "<redacted>" in safe


def test_collect_upload_diagnostics_uses_safe_env_only(monkeypatch):
    monkeypatch.setenv("SPACE_ID", "owner/space")
    monkeypatch.setenv("HF_TOKEN", "do-not-render")
    monkeypatch.setenv("GROQ_API_KEY", "do-not-render")

    diagnostics = collect_upload_diagnostics(None)

    assert diagnostics["env"]["SPACE_ID"] == "owner/space"
    assert "HF_TOKEN" not in diagnostics["env"]
    assert "GROQ_API_KEY" not in diagnostics["env"]
    assert diagnostics_are_secret_safe(diagnostics)


def test_streamlit_config_contains_upload_fallback_settings():
    config = Path(".streamlit/config.toml").read_text(encoding="utf-8")

    assert 'address = "0.0.0.0"' in config
    assert "enableCORS = false" in config
    assert "enableXsrfProtection = false" in config
    assert "maxUploadSize = 25" in config
    assert "maxMessageSize = 25" in config
