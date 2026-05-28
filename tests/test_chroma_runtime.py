from pathlib import Path

import pytest

from chroma_runtime import (
    LOCAL_RUNTIME_ROOT,
    cleanup_local_chroma_runtime,
    describe_chroma_runtime_mode,
    get_chroma_runtime_dir,
    is_snapshot_update_allowed,
    prepare_readonly_chroma_runtime,
)


def _make_fake_chroma_dir(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "chroma.sqlite3").write_text("fake sqlite", encoding="utf-8")
    (path / "index").mkdir()
    (path / "index" / "data.bin").write_text("fake index", encoding="utf-8")
    return path


def test_get_chroma_runtime_dir_defaults_to_snapshot_path(tmp_path):
    snapshot = _make_fake_chroma_dir(tmp_path / "snapshot")

    runtime = get_chroma_runtime_dir(snapshot, env={})

    assert Path(runtime).resolve() == snapshot.resolve()


def test_get_chroma_runtime_dir_uses_local_copy_when_enabled(tmp_path):
    snapshot = _make_fake_chroma_dir(tmp_path / "snapshot")

    runtime = Path(get_chroma_runtime_dir(snapshot, env={"CHROMA_USE_LOCAL_COPY": "1"}))

    assert ".local_chroma_runtime" in runtime.parts
    assert runtime.resolve() != snapshot.resolve()
    assert (runtime / "chroma.sqlite3").exists()


def test_local_copy_target_cannot_escape_runtime_root(tmp_path):
    snapshot = _make_fake_chroma_dir(tmp_path / "snapshot")

    with pytest.raises(ValueError):
        prepare_readonly_chroma_runtime(snapshot, tmp_path / "outside")


def test_snapshot_update_requires_explicit_flag():
    assert is_snapshot_update_allowed({}) is False
    assert is_snapshot_update_allowed({"CHROMA_ALLOW_SNAPSHOT_UPDATE": "1"}) is True


def test_describe_chroma_runtime_mode_has_no_secret_values(tmp_path):
    snapshot = _make_fake_chroma_dir(tmp_path / "snapshot")

    description = describe_chroma_runtime_mode(
        snapshot,
        env={"CHROMA_USE_LOCAL_COPY": "1", "GROQ_API_KEY": "should-not-appear"},
    )

    joined = " ".join(str(value) for value in description.values())
    assert description["mode"] == "local_copy"
    assert "should-not-appear" not in joined
    assert "GROQ_API_KEY" not in joined


def test_missing_source_dir_raises_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        get_chroma_runtime_dir(tmp_path / "missing", env={"CHROMA_USE_LOCAL_COPY": "1"})


def test_cleanup_local_chroma_runtime_removes_ignored_copy(tmp_path):
    snapshot = _make_fake_chroma_dir(tmp_path / "snapshot")
    runtime = Path(get_chroma_runtime_dir(snapshot, env={"CHROMA_USE_LOCAL_COPY": "1"}))

    assert runtime.exists()
    cleanup_local_chroma_runtime()

    assert not LOCAL_RUNTIME_ROOT.exists()
