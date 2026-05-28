"""ChromaDB runtime path helpers.

The tracked ``chroma_db/`` directory is the snapshot source of truth. During
normal local evaluation, ``CHROMA_USE_LOCAL_COPY=1`` can redirect runtime reads
to ``.local_chroma_runtime/chroma_db`` so Chroma internals do not dirty the
tracked snapshot files.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_SNAPSHOT_DIR = ROOT_DIR / "chroma_db"
LOCAL_RUNTIME_ROOT = ROOT_DIR / ".local_chroma_runtime"
LOCAL_RUNTIME_DB_DIR = LOCAL_RUNTIME_ROOT / "chroma_db"

TRUTHY_VALUES = {"1", "true", "yes", "on"}


def _is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in TRUTHY_VALUES


def _resolve_under_root(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError(f"Local Chroma runtime path escapes {root_resolved}")
    return resolved


def is_local_copy_enabled(env: dict[str, str] | None = None) -> bool:
    """Return True when local Chroma copy mode is enabled."""

    env = os.environ if env is None else env
    return _is_truthy(env.get("CHROMA_USE_LOCAL_COPY"))


def is_snapshot_update_allowed(env: dict[str, str] | None = None) -> bool:
    """Return True only for explicit snapshot mutation/update workflows."""

    env = os.environ if env is None else env
    return _is_truthy(env.get("CHROMA_ALLOW_SNAPSHOT_UPDATE"))


def prepare_readonly_chroma_runtime(
    source_dir: str | os.PathLike[str] | None = None,
    target_dir: str | os.PathLike[str] | None = None,
) -> Path:
    """Copy the tracked snapshot to a local ignored runtime directory."""

    source = Path(source_dir or DEFAULT_SNAPSHOT_DIR).resolve()
    target = _resolve_under_root(Path(target_dir or LOCAL_RUNTIME_DB_DIR), LOCAL_RUNTIME_ROOT)

    if not source.is_dir():
        raise FileNotFoundError(f"Chroma snapshot directory not found: {source}")
    if not (source / "chroma.sqlite3").exists():
        raise FileNotFoundError(f"Chroma snapshot sqlite not found: {source / 'chroma.sqlite3'}")

    target.parent.mkdir(parents=True, exist_ok=True)
    if not (target / "chroma.sqlite3").exists():
        shutil.copytree(source, target, dirs_exist_ok=True)
    return target


def get_chroma_runtime_dir(
    snapshot_dir: str | os.PathLike[str] | None = None,
    env: dict[str, str] | None = None,
) -> str:
    """Return the Chroma persist directory for the current runtime mode."""

    env = os.environ if env is None else env
    snapshot = Path(snapshot_dir or DEFAULT_SNAPSHOT_DIR).resolve()
    if not is_local_copy_enabled(env):
        return str(snapshot)
    return str(prepare_readonly_chroma_runtime(snapshot))


def cleanup_local_chroma_runtime(target_root: str | os.PathLike[str] | None = None) -> None:
    """Remove the ignored local Chroma runtime copy."""

    root = _resolve_under_root(Path(target_root or LOCAL_RUNTIME_ROOT), LOCAL_RUNTIME_ROOT)
    if root.exists():
        shutil.rmtree(root)


def describe_chroma_runtime_mode(
    snapshot_dir: str | os.PathLike[str] | None = None,
    env: dict[str, str] | None = None,
) -> dict:
    """Describe runtime path selection without exposing secret values."""

    env = os.environ if env is None else env
    snapshot = Path(snapshot_dir or DEFAULT_SNAPSHOT_DIR).resolve()
    use_local_copy = is_local_copy_enabled(env)
    runtime_dir = Path(get_chroma_runtime_dir(snapshot, env)).resolve()
    return {
        "mode": "local_copy" if use_local_copy else "tracked_snapshot",
        "use_local_copy": use_local_copy,
        "snapshot_dir": str(snapshot),
        "runtime_dir": str(runtime_dir),
        "local_runtime_root": str(LOCAL_RUNTIME_ROOT.resolve()),
        "snapshot_update_allowed": is_snapshot_update_allowed(env),
    }
