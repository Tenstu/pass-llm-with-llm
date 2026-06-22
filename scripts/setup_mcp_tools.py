#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
MCP 增强工具安装/配置脚本。

用法:
  python setup_mcp_tools.py --recommended
  python setup_mcp_tools.py --all
  python setup_mcp_tools.py --exam-memory-only
  python setup_mcp_tools.py --configure-installed-external
  python setup_mcp_tools.py --check
  python setup_mcp_tools.py --install chatmem
  python setup_mcp_tools.py --config-only onefind
  python setup_mcp_tools.py --remove chatmem
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
MCP_CONFIG_PATH = REPO_ROOT / ".mcp.json"
MCP_EXAMPLE_PATH = REPO_ROOT / ".mcp.example.json"


@dataclass
class ToolInfo:
    """Metadata for one MCP tool."""
    name: str
    description: str
    install_hint: str
    check_func: Any = None
    config_func: Any = None


# ── detection functions ────────────────────────────────────────────

def _check_exam_memory() -> bool:
    server = REPO_ROOT / "shared" / "exam_memory" / "server.py"
    return server.exists()


def _check_chatmem() -> bool:
    paths = [
        Path("D:/Programe/chatmem/ChatMem.exe"),
        Path("D:/Programe/chatmem/chatmem-mcp.exe"),
    ]
    return any(p.exists() for p in paths)


def _check_mempalace() -> bool:
    return shutil.which("mempalace-mcp") is not None or shutil.which("mempalace") is not None


def _check_onefind() -> bool:
    return Path("D:/tools/onefind").exists() and (Path("D:/tools/onefind") / "kb_ask.cmd").exists()


# ── config generators ──────────────────────────────────────────────

def _cfg_exam_memory() -> dict:
    return {
        "command": sys.executable,
        "args": [
            str(REPO_ROOT / "shared" / "exam_memory" / "server.py"),
        ],
        "cwd": str(REPO_ROOT),
        "env": {
            "CUDA_VISIBLE_DEVICES": "",
            "HF_HUB_ENABLE_HF_TRANSFER": "0",
        },
    }


def _cfg_chatmem() -> dict:
    exe_path = "D:/Programe/chatmem/ChatMem.exe"
    if Path("D:/Programe/chatmem/chatmem-mcp.exe").exists():
        return {
            "command": "D:/Programe/chatmem/chatmem-mcp.exe",
            "args": [],
        }
    return {
        "command": "D:/Programe/chatmem/ChatMem.exe",
        "args": ["--mcp"],
    }


def _cfg_mempalace() -> dict:
    mcp_bin = shutil.which("mempalace-mcp")
    if mcp_bin:
        return {
            "command": mcp_bin,
            "args": [],
        }
    if sys.platform == "win32":
        py_launcher = shutil.which("py")
        if py_launcher:
            return {
                "command": py_launcher,
                "args": ["-3.11", "-m", "mempalace.mcp_server"],
            }
        return {
            "command": sys.executable,
            "args": ["-m", "mempalace.mcp_server"],
        }
    return {
        "command": sys.executable,
        "args": ["-m", "mempalace.mcp_server"],
    }


def _cfg_onefind() -> dict:
    return {
        "command": "D:/tools/onefind/kb_bootstrap_runtime.cmd",
        "args": [],
        "cwd": "D:/tools/onefind",
    }


TOOLS: list[ToolInfo] = [
    ToolInfo(
        name="exam-memory",
        description="项目自带 MCP — 跨会话错题持久化、语义检索、用户画像",
        install_hint="cd shared/exam_memory && pip install -e '.[embed]'",
        check_func=_check_exam_memory,
        config_func=_cfg_exam_memory,
    ),
    ToolInfo(
        name="chatmem",
        description="ChatMem — 对话级记忆，用于交接/继续/项目历史回忆",
        install_hint="从 https://github.com/Rimagination/ChatMem/releases 下载 ChatMem.exe，放置于 D:\\Programe\\chatmem\\",
        check_func=_check_chatmem,
        config_func=_cfg_chatmem,
    ),
    ToolInfo(
        name="mempalace",
        description="MemPalace — 长期结构化知识存储与知识图谱",
        install_hint="pip install mempalace",
        check_func=_check_mempalace,
        config_func=_cfg_mempalace,
    ),
    ToolInfo(
        name="onefind",
        description="OneFind — 外部本地知识库检索（Obsidian/Zotero/文件夹等）",
        install_hint="从 https://github.com/iawnfoanaowt/OneFind/releases 下载并解压到 D:\\tools\\onefind\\",
        check_func=_check_onefind,
        config_func=_cfg_onefind,
    ),
]

TOOL_MAP: dict[str, ToolInfo] = {t.name: t for t in TOOLS}
EXTERNAL_TOOL_NAMES = ("chatmem", "mempalace", "onefind")


# ── core operations ────────────────────────────────────────────────

def load_config() -> dict:
    if MCP_CONFIG_PATH.exists():
        return json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8"))
    return {"mcpServers": {}}


def save_config(cfg: dict) -> None:
    MCP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    MCP_CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def check_all() -> dict[str, dict]:
    results = {}
    for tool in TOOLS:
        installed = tool.check_func()
        results[tool.name] = {
            "installed": installed,
            "description": tool.description,
            "install_hint": tool.install_hint,
        }
    return results


def install_tool(name: str, force: bool = False) -> tuple[bool, str]:
    if name not in TOOL_MAP:
        return False, f"未知工具: {name}"

    tool = TOOL_MAP[name]

    if tool.check_func() and not force:
        return True, f"{name} 已安装，跳过"

    if name == "exam-memory":
        return _pip_install_exam_memory()
    elif name == "chatmem":
        return False, (
            f"ChatMem 需要手动安装。请从 GitHub Releases 下载 ChatMem.exe 放置于 D:\\Programe\\chatmem\\\n"
            f"下载地址: https://github.com/Rimagination/ChatMem/releases"
        )
    elif name == "mempalace":
        return _pip_install_mempalace()
    elif name == "onefind":
        return False, (
            f"OneFind 需要手动安装。请从 GitHub Releases 下载并解压到 D:\\tools\\onefind\\\n"
            f"下载地址: https://github.com/iawnfoanaowt/OneFind/releases"
        )

    return False, "未实现的安装逻辑"


def _pip_install_exam_memory() -> tuple[bool, str]:
    target = REPO_ROOT / "shared" / "exam_memory"
    if not target.exists():
        return False, f"目录不存在: {target}"
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", ".[embed,generate]"],
            cwd=str(target),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            return True, "exam-memory 安装成功"
        return False, f"pip 安装失败: {result.stderr[-500:]}"
    except Exception as e:
        return False, str(e)


def _pip_install_mempalace() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "mempalace"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return True, "mempalace 安装成功"
        return False, f"pip 安装失败: {result.stderr[-500:]}"
    except Exception as e:
        return False, str(e)


def configure_tool(name: str) -> tuple[bool, str]:
    """Add tool config to .mcp.json if it's not already there."""
    if name not in TOOL_MAP:
        return False, f"未知工具: {name}"

    tool = TOOL_MAP[name]
    cfg = load_config()
    servers = cfg.setdefault("mcpServers", {})

    if name in servers:
        return True, f"{name} 已在 .mcp.json 中，跳过配置"

    try:
        servers[name] = tool.config_func()
        save_config(cfg)
        return True, f"{name} 已写入 .mcp.json"
    except Exception as e:
        return False, f"配置失败: {e}"


def remove_tool(name: str) -> tuple[bool, str]:
    cfg = load_config()
    servers = cfg.setdefault("mcpServers", {})
    if name in servers:
        del servers[name]
        save_config(cfg)
        return True, f"{name} 已从 .mcp.json 移除"
    return True, f"{name} 不在 .mcp.json 中，无需移除"


def setup_all() -> dict[str, dict]:
    """Try to install and configure all tools. External tools may still need manual install."""
    report = {}
    for tool in TOOLS:
        ok, msg = install_tool(tool.name)
        report[tool.name] = {"install": (ok, msg)}
        if ok:
            ok2, msg2 = configure_tool(tool.name)
            report[tool.name]["config"] = (ok2, msg2)
        else:
            report[tool.name]["config"] = (False, "安装未完成，跳过配置")
    return report


def configure_installed_external() -> dict[str, dict]:
    """Configure external tools only when they are already present on this machine."""
    report = {}
    for name in EXTERNAL_TOOL_NAMES:
        tool = TOOL_MAP[name]
        installed = tool.check_func()
        if not installed:
            report[name] = {
                "check": (False, f"未检测到，跳过配置。安装方式: {tool.install_hint}")
            }
            continue
        report[name] = {"check": (True, "已检测到本机安装")}
        ok, msg = configure_tool(name)
        report[name]["config"] = (ok, msg)
    return report


def setup_exam_memory_only() -> dict[str, dict]:
    report = {}
    tool = TOOL_MAP["exam-memory"]
    ok, msg = install_tool(tool.name)
    report[tool.name] = {"install": (ok, msg)}
    if ok:
        ok2, msg2 = configure_tool(tool.name)
        report[tool.name]["config"] = (ok2, msg2)
    else:
        report[tool.name]["config"] = (False, "安装未完成，跳过配置")
    return report


# ── CLI ────────────────────────────────────────────────────────────

def _make_stdio_safe() -> None:
    """Avoid UnicodeEncodeError in legacy Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")


def _print_report(report: dict[str, dict]) -> None:
    print()
    for name, steps in report.items():
        status = "[OK]" if all(ok for ok, _ in steps.values()) else "[WARN]"
        print(f"  {status} {name}")
        for step, (ok, msg) in steps.items():
            step_status = "[OK]" if ok else "[FAIL]"
            print(f"    {step_status} {step}: {msg}")


def main():
    _make_stdio_safe()

    parser = argparse.ArgumentParser(
        description="MCP 增强工具安装/配置脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--recommended", action="store_true", help="安装推荐增强项（exam-memory）")
    parser.add_argument("--all", action="store_true", help="高级：尝试安装并配置所有工具；外部工具缺失时只提示")
    parser.add_argument("--exam-memory-only", action="store_true", help="仅安装 exam-memory")
    parser.add_argument("--configure-installed-external", action="store_true", help="仅配置已手动安装的外部工具")
    parser.add_argument("--check", action="store_true", help="检查各工具安装状态")
    parser.add_argument("--install", metavar="NAME", help="安装指定工具")
    parser.add_argument("--remove", metavar="NAME", help="从 .mcp.json 移除指定工具")
    parser.add_argument("--config-only", metavar="NAME", help="仅写入 .mcp.json 配置（不安装）")
    parser.add_argument("--force", action="store_true", help="强制重新安装")

    args = parser.parse_args()

    if args.check:
        results = check_all()
        print("MCP 工具安装状态检查:")
        print()
        for name, info in results.items():
            status = "[OK]" if info["installed"] else "[MISSING]"
            print(f"  {status} {name}: {info['description']}")
            if not info["installed"]:
                print(f"      安装方式: {info['install_hint']}")
        print()
        return

    if args.all:
        print("正在尝试安装全部 MCP 工具（外部工具缺失时只提示，不阻塞 exam-memory）...")
        report = setup_all()
        _print_report(report)

    elif args.recommended or args.exam_memory_only:
        print("正在安装 exam-memory...")
        report = setup_exam_memory_only()
        _print_report(report)

    elif args.configure_installed_external:
        print("正在配置已安装的外部 MCP 工具...")
        report = configure_installed_external()
        _print_report(report)

    elif args.install:
        ok, msg = install_tool(args.install, force=args.force)
        status = "[OK]" if ok else "[FAIL]"
        print(f"  {status} {args.install}: {msg}")
        if ok:
            ok2, msg2 = configure_tool(args.install)
            status2 = "[OK]" if ok2 else "[FAIL]"
            print(f"  {status2} config: {msg2}")

    elif args.remove:
        ok, msg = remove_tool(args.remove)
        status = "[OK]" if ok else "[FAIL]"
        print(f"  {status} {msg}")

    elif args.config_only:
        ok, msg = configure_tool(args.config_only)
        status = "[OK]" if ok else "[FAIL]"
        print(f"  {status} {msg}")

    else:
        # Default: check all
        args.check = True
        results = check_all()
        print("MCP 工具安装状态:")
        print()
        for name, info in results.items():
            status = "[OK]" if info["installed"] else "[MISSING]"
            print(f"  {status} {name}: {info['description']}")
            if not info["installed"]:
                print(f"      安装方式: {info['install_hint']}")
        print()
        not_installed = [n for n, i in results.items() if not i["installed"]]
        if not_installed:
            print(f"  未安装: {', '.join(not_installed)}")
            print("  推荐使用 --recommended 启用项目自带 exam-memory。")
            print("  外部工具请先手动安装，再用 --configure-installed-external 或 --config-only <name> 注册。")


if __name__ == "__main__":
    main()
