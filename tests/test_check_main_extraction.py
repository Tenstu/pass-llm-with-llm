"""Tests for the main-extraction denylist gate."""

from types import SimpleNamespace

from scripts import check_main_extraction
from scripts.check_main_extraction import _git_staged, _matches_denylist


def test_target_wildcards_do_not_match_unrelated_target_files():
    allowed = [
        "targets/exam_config_template.md",
        "targets/ai-lab/exam_config.md",
        "shared/exam_memory/server.py",
        "README.md",
        "README_EN.md",
        "HANDOFF.example.md",
    ]

    for path in allowed:
        assert _matches_denylist(path) is None


def test_target_file_wildcards_match_exact_single_target_segment():
    assert _matches_denylist("targets/ai-lab/mistake_log.md") == "targets/*/mistake_log.md"
    assert _matches_denylist(r"targets\ai-lab\mock_exam_log.md") == "targets/*/mock_exam_log.md"
    assert _matches_denylist("targets/foo/bar/mistake_log.md") is None


def test_target_directory_wildcards_match_directory_and_children():
    assert _matches_denylist("targets/ai-lab/progress") == "targets/*/progress/"
    assert _matches_denylist("targets/ai-lab/progress/rounds/r1.md") == "targets/*/progress/"
    assert _matches_denylist("targets/ai-lab/cheatsheets/math_fundamentals.md") == "targets/*/cheatsheets/"
    assert _matches_denylist("targets/ai-lab/sources/source_index.md") == "targets/*/sources/"
    assert _matches_denylist("targets/foo/bar/progress/r1.md") is None


def test_plain_directory_denylist_matches_nested_children():
    assert _matches_denylist("docs") == "docs/"
    assert _matches_denylist("docs/archive/dev-branch-review.md") == "docs/"
    assert _matches_denylist("skills/branch-ops/SKILL.md") == "skills/branch-ops/"
    assert (
        _matches_denylist("skills/branch-ops/references/branch-workflow.md")
        == "skills/branch-ops/"
    )


def test_runtime_bank_stats_are_dev_only():
    assert (
        _matches_denylist("shared/exam_memory/bank/difficulty_stats.json")
        == "shared/exam_memory/bank/difficulty_stats.json"
    )


def test_dev_only_regression_tests_are_not_public_extraction_candidates():
    blocked = [
        "tests/test_chunking.py",
        "tests/test_fts_store.py",
        "tests/test_hybrid_search.py",
        "tests/test_security.py",
        "tests/test_server.py",
        "tests/test_vector_store.py",
    ]

    for path in blocked:
        assert _matches_denylist(path) == path


def test_sensitive_root_config_is_dev_only_with_public_examples_allowed():
    blocked = [".mcp.json", ".env", ".env.local", ".env.production"]
    for path in blocked:
        assert _matches_denylist(path) is not None

    assert _matches_denylist(".mcp.example.json") is None
    assert _matches_denylist(".env.example") is None


def test_bank_runtime_markdown_is_dev_only_except_readme():
    assert _matches_denylist("shared/exam_memory/bank/custom.md") == "shared/exam_memory/bank/"
    assert _matches_denylist("shared/exam_memory/bank/nested/custom.md") == "shared/exam_memory/bank/"
    assert _matches_denylist("shared/exam_memory/bank/README.md") is None


def test_target_solutions_and_handoff_require_manual_sanitization():
    assert _matches_denylist("targets/ai-lab/solutions/foo.md") == "targets/*/solutions/"
    assert _matches_denylist("targets/foo/bar/solutions/foo.md") is None
    assert _matches_denylist("HANDOFF.md") == "HANDOFF.md"


def test_shared_progress_public_allowlist_keeps_templates_publishable():
    allowed = [
        "shared/progress/foo.example.md",
        "shared/progress/README.md",
        r"shared\progress\task-board\.gitkeep",
        "shared/progress/task-board/task-board.example.md",
        "shared/progress/reviews/review.template.md",
    ]

    for path in allowed:
        assert _matches_denylist(path) is None


def test_shared_progress_blocks_runtime_records_even_if_force_added():
    blocked = [
        "shared/progress/task-board.md",
        "shared/progress/task-board/task-board.md",
        "shared/progress/foo.example.md.bak",
        "shared/progress/foo.md",
        "shared/progress/.env.example",
        "shared/progress/choice-questions/round2.md",
        "shared/progress/reviews/review-2026-06-20.md",
    ]

    for path in blocked:
        assert _matches_denylist(path) == "shared/progress/"


def test_main_reports_only_blocked_paths_from_mixed_explicit_list(monkeypatch, capsys):
    monkeypatch.setattr(
        check_main_extraction.sys,
        "argv",
        [
            "check_main_extraction.py",
            "--staged-files",
            "shared/progress/README.md",
            "shared/progress/task-board/task-board.example.md",
            "shared/progress/task-board/task-board.md",
        ],
    )

    assert check_main_extraction.main() == 1
    captured = capsys.readouterr()
    assert "shared/progress/task-board/task-board.md" in captured.err
    assert "shared/progress/README.md" not in captured.err
    assert "shared/progress/task-board/task-board.example.md" not in captured.err


def test_git_staged_ignores_deletions(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout="README.md\n")

    monkeypatch.setattr(check_main_extraction.subprocess, "run", fake_run)

    assert _git_staged() == ["README.md"]
    assert "--diff-filter=ACMRTUXB" in calls[0]


def test_main_rejects_wrong_required_branch(monkeypatch, capsys):
    monkeypatch.setattr(
        check_main_extraction.sys,
        "argv",
        ["check_main_extraction.py", "--require-branch", "main", "--staged-files", "README.md"],
    )
    monkeypatch.setattr(check_main_extraction, "_git_current_branch", lambda: "dev")

    assert check_main_extraction.main() == 1
    assert "WRONG BRANCH" in capsys.readouterr().err


def test_main_accepts_required_branch(monkeypatch, capsys):
    monkeypatch.setattr(
        check_main_extraction.sys,
        "argv",
        ["check_main_extraction.py", "--require-branch", "main", "--staged-files", "README.md"],
    )
    monkeypatch.setattr(check_main_extraction, "_git_current_branch", lambda: "main")

    assert check_main_extraction.main() == 0
    assert "no denylist violations" in capsys.readouterr().out
