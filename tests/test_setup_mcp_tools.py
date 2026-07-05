"""Tests for MCP setup helper behavior."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


def _load_setup_module():
    path = Path(__file__).resolve().parent.parent / "scripts" / "setup_mcp_tools.py"
    spec = importlib.util.spec_from_file_location("setup_mcp_tools", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_exam_memory_check_requires_importable_package(monkeypatch, tmp_path):
    setup = _load_setup_module()
    server = tmp_path / "shared" / "exam_memory" / "server.py"
    server.parent.mkdir(parents=True)
    server.write_text("# placeholder\n", encoding="utf-8")

    monkeypatch.setattr(setup, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        setup.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1),
    )

    assert setup._check_exam_memory() is False


def test_exam_memory_check_passes_when_package_imports(monkeypatch, tmp_path):
    setup = _load_setup_module()
    server = tmp_path / "shared" / "exam_memory" / "server.py"
    server.parent.mkdir(parents=True)
    server.write_text("# placeholder\n", encoding="utf-8")

    monkeypatch.setattr(setup, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        setup.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )

    assert setup._check_exam_memory() is True


def test_yes_no_prompt_accepts_default_and_clear_no():
    setup = _load_setup_module()

    assert setup._answer_yes("") is True
    assert setup._answer_yes("Y") is True
    assert setup._answer_yes("no") is False
