# pass-llm-with-llm

> Use LLM to pass LLM exams — a Claude Code Skills + MCP powered AI exam preparation engine

[中文文档](README_CN.md)

## What Is This

An **execution harness**, not a knowledge base. It chains Claude Code's Skill mechanism into an automated closed loop: algorithm skeleton generation → solution diagnosis → annotation → mistake tracking → targeted question drilling.

Built for AI/算法岗位笔试 preparation, but the core Skill Pipeline is exam-agnostic and can be adapted to any written exam target.

## Core Features

- **Skill Pipeline**: solve-skeleton → solve-analyze → algo-annotation — full chain from problem to annotated solution
- **Mistake Feedback Loop**: WA/TLE errors auto-recorded, next problem auto-annotated with `# [防错]` markers
- **Choice Question Engine**: targeted generation → interactive drill → instant scoring → weakness analysis
- **MCP Experience Persistence** (optional): cross-session error pattern storage + user profiling via custom MCP Server
- **Progress Tracking**: readiness score, coverage gaps, daily must-do list

## Quick Start

### Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI or VS Code extension
- Python 3.10+ (only needed for MCP Server)

### Supported Environments

| Component | Details |
|-----------|---------|
| IDE | VS Code (**recommended** — interactive quiz mode requires VS Code extension) or terminal |
| Claude Code | VS Code extension (**recommended**) or CLI (`npm install -g @anthropic-ai/claude-code`) |
| Model Provider | Any provider supported by Claude Code (Claude API, third-party, local) |
| Python | 3.10+ (only for exam-memory MCP Server) |

This project was developed using the **Claude Code VS Code extension** with third-party model providers (Xiaomi mimo-v2.5-pro, StepFun step-3.7-flash). The Skill Pipeline is model-agnostic — any capable model works. See [Environment Support](docs/environment-support.md) for details.

### Install

```bash
git clone https://github.com/Tenstu/pass-llm-with-llm.git
cd pass-llm-with-llm
```

### Configure Your Target Exam

Edit `HANDOFF.md` with your exam name, date, and daily study hours. Update `sources/` with your exam's historical patterns.

### Use

1. Open the project in Claude Code
2. **First time?** Say "init" or "初始化" to launch the onboarding guide — it collects your exam target, date, and scope
3. Daily use: read `START_HERE.md` for session bootstrap
4. For algorithm problems: `Skill(skill="solve-skeleton")`
5. For diagnosis: `Skill(skill="solve-analyze")`
6. For choice questions: `Skill(skill="choice-q-create")` → `Skill(skill="choice-q-drill")`

### Startup Order

```
git clone → cd pass-llm-with-llm
  │
  ├── pip install mcp               # optional: for exam-memory MCP server
  │
  ├── edit .mcp.json                # register exam-memory (see docs/mcp-setup-guide.md)
  │
  ├── open in Claude Code
  │     │
  │     ├── first time → say "init" → init-guide Skill walks you through setup
  │     │
  │     └── daily use → read START_HERE.md → Skill Pipeline
  │
  └── (optional) configure external MCPs: ChatMem, mempalace, onefind
        these are environment-level, not project-bundled
        see docs/mcp-setup-guide.md for references
```

### MCP Dependencies

This project **bundles one MCP server** (`exam-memory`) and **references external MCPs** that are not included:

| MCP Server | Bundled? | Purpose | Setup |
|------------|:---:|---------|-------|
| `exam-memory` | Yes | Cross-session experience persistence + user profiling | `pip install mcp` + edit `.mcp.json` |
| ChatMem | No | Cross-session conversation memory | [External install](https://github.com/Rimagination/ChatMem/releases) |
| mempalace | No | Structured knowledge storage | [External install](https://github.com/MemPalace/mempalace) |
| onefind | No | Local knowledge base retrieval | [External install](https://github.com/iawnfoanaowt/OneFind) |

All skills degrade gracefully to local-only mode when MCP is unavailable. See [MCP Setup Guide](docs/mcp-setup-guide.md) for full configuration instructions.

## Skill Reference

| Skill | Purpose | MCP Required |
|-------|---------|:---:|
| init-guide | First-run onboarding: exam target, date, scope, user profiling | Optional |
| solve-skeleton | Algorithm problem skeleton generation (8 templates + 6 patterns) | No |
| solve-analyze | Diagnosis: code comparison + root cause tagging | Optional |
| algo-annotation | Chinese comments + `# [防错]` markers | No |
| choice-q-create | Targeted choice question generation | Optional |
| choice-q-drill | Interactive quiz + instant scoring | Optional |
| exam-assistant | Exam assistant with experience retrieval + user profiling | Yes |
| review-tracker | Progress aggregation + readiness trends | No |

All skills with "Optional" MCP degrade gracefully to local-only mode when MCP is unavailable.

### ChatMem Enhancement (Recommended)

[ChatMem](https://github.com/Rimagination/ChatMem/releases) provides cross-session conversation memory. While not required, it significantly improves these skills:

| Skill | With ChatMem |
|-------|-------------|
| review-tracker | Stores historical progress reports; enables cross-session trend comparison |
| exam-assistant | Recalls prior quiz sessions and error discussions for continuity |
| init-guide | Remembers previous onboarding attempts; avoids re-collecting known info |
| solve-analyze | Links diagnosis history across sessions for pattern recognition |

Install ChatMem and register it in your Claude Code global config. See [MCP Setup Guide](docs/mcp-setup-guide.md).

## Roadmap

### V1 (Current) — Stable

- Skill Pipeline: solve-skeleton / solve-analyze / algo-annotation
- Choice question engine: create / drill / scoring
- exam-memory MCP V1: local file-based experience CRUD + user profiling
- Progress tracking and mistake feedback loop

### V2 — RAG + Semantic Retrieval

Upgrade `exam-memory` from keyword matching to semantic search:

| Phase | Feature | Dependencies |
|-------|---------|--------------|
| 1 | Experience auto-vectorization → ChromaDB | `chromadb`, `langchain` |
| 2 | `list_experiences` supports semantic retrieval | Phase 1 |
| 3 | LangChain Agent auto-infers user profile | `langchain`, LLM API |
| 4 | Knowledge graph for prerequisite recommendations | Phase 1 |

### V3 — Long-term Directions

- **Multimodal**: screenshot OCR → auto problem-type detection + experience retrieval
- **Spaced repetition**: SM-2 based review scheduling
- **Cross-device sync**: Git or WebDAV for experience files
- **Analytics dashboard**: strength/weakness heatmap, error trends, review plan

### Open Source Improvements

- GitHub issue & PR templates (`.github/`)
- `CHANGELOG.md`

## Directory Structure

```
pass-llm-with-llm/
  AGENTS.md                    # Project rules, Component Map, Skill Pipeline
  START_HERE.md                # Session bootstrap + Skill invocation guide
  HANDOFF.md                   # Session handoff template
  README.md                    # This file (English)
  README_CN.md                 # Chinese documentation

  skills/                      # Claude Code Skill definitions
    init-guide.md              # First-run onboarding (exam target, date, scope)
    solve-skeleton/            # Algorithm skeleton templates
    solve-analyze/             # Solution diagnosis engine
    algo-annotation.md         # Code annotation with mistake markers
    choice-q-create.md         # Choice question generator
    choice-q-drill.md          # Interactive quiz mode
    exam-assistant.md          # MCP-backed exam assistant
    review-tracker.md          # Progress aggregation

  algorithms/                  # OJ code assets
    python_oj_template.py      # Utility function library
    solutions_batch.py         # Exam problem solution collection
    practice/                  # Practice problems by topic
    mistake_log.md             # WA/TLE error patterns
    topic_checklist.md         # Topic coverage tracking

  llm/                         # AI/ML quick-reference notes
    llm_core_cheatsheet.md     # Transformer, SFT/LoRA, RLHF, RAG, KV cache
    gnn_diffusion_cheatsheet.md
    math_fundamentals.md
    ai_lab_context.md          # Target company/lab background

  exam_memory/                 # Custom MCP Server (optional)
    server.py                  # 6 MCP tools for experience persistence
    experiences/               # Experience files (YAML frontmatter + Markdown)
    user_profile.json          # User strengths/weaknesses/preferences

  daily/                       # Daily plans (YYYY-MM-DD.md)
  progress/                    # Progress tracking by category
  sources/                     # External reference materials
  prompts/                     # Prompt templates
  docs/                        # Design documents, setup guides, and license
    mcp-setup-guide.md         # MCP configuration: exam-memory + external MCP references
```

## Adapting to Other Exams

The framework defaults to AI Lab exam format but is designed to be reconfigured:

1. Replace `sources/ai_lab_history_problems.md` with your target exam's pattern analysis
2. Update `skills/choice-q-create.md` question generation parameters
3. Swap `llm/` notes with your domain's core knowledge
4. Adjust `AGENTS.md` Exam Format table

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE)
