import json
import subprocess
import sys

from evaluation.run_regression_suite import PROFILE_STEPS, get_profile_steps, run_profile


def test_required_profiles_are_defined():
    for profile in ("fast", "full", "dynamic-source", "snapshot-update", "grounding"):
        assert profile in PROFILE_STEPS
        assert get_profile_steps(profile)


def test_default_profiles_do_not_enable_live_calls():
    report = run_profile("fast", dry_run=True)

    assert report["live_llm"] is False
    assert report["dynamic_live_fetch"] is False
    assert all("--live-llm" not in step["command"] for step in report["steps"])
    assert all("--live-fetch" not in step["command"] for step in report["steps"])


def test_full_profile_includes_answer_grounding_without_live_llm():
    report = run_profile("full", dry_run=True)

    commands = [step["command"] for step in report["steps"]]
    assert any("evaluate_answer_grounding.py" in command for command in commands)
    assert all("--live-llm" not in command for command in commands)


def test_local_chroma_copy_flag_is_reported_in_dry_run():
    report = run_profile("fast", dry_run=True, use_local_chroma_copy=True)

    assert report["use_local_chroma_copy"] is True
    assert all("CHROMA_USE_LOCAL_COPY" in step["env_overrides"] for step in report["steps"])


def test_dry_run_builds_report_without_running_commands():
    report = run_profile("full", dry_run=True)

    assert report["status"] == "passed"
    assert report["total_steps"] == len(PROFILE_STEPS["full"])
    assert report["skipped"] == len(PROFILE_STEPS["full"])
    assert report["steps"]
    assert all(step["status"] == "skipped" for step in report["steps"])


def test_list_profiles_cli_outputs_known_profiles():
    completed = subprocess.run(
        [sys.executable, "evaluation/run_regression_suite.py", "--list-profiles"],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0
    assert "fast" in completed.stdout
    assert "snapshot-update" in completed.stdout


def test_dry_run_cli_writes_valid_report(tmp_path):
    json_out = tmp_path / "regression.local.json"
    markdown_out = tmp_path / "regression.local.md"

    completed = subprocess.run(
        [
            sys.executable,
            "evaluation/run_regression_suite.py",
            "--profile",
            "fast",
            "--dry-run",
            "--out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0
    report = json.loads(json_out.read_text(encoding="utf-8"))
    assert report["profile"] == "fast"
    assert isinstance(report["steps"], list)
    assert report["steps"]
    assert markdown_out.read_text(encoding="utf-8").startswith("# Regression Suite Summary")


def test_unknown_profile_cli_returns_error():
    completed = subprocess.run(
        [sys.executable, "evaluation/run_regression_suite.py", "--profile", "unknown"],
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "invalid choice" in completed.stderr
