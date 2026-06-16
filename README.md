# Pass-LLM-with-LLM

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
git clone https://github.com/Tenstu/Pass-LLM-with-LLM.git
cd Pass-LLM-with-LLM
```

### Use

1. Open the project in Claude Code
2. **First time?** Say "init" or "初始化" — the init-guide skill will collect your exam target, date, and daily study hours, then configure `HANDOFF.md`, `sources/`, `AGENTS.md`, and user profile automatically
3. Daily use: read `START_HERE.md` for session bootstrap
4. For algorithm problems: `Skill(skill="solve-skeleton")`
5. For diagnosis: `Skill(skill="solve-analyze")`
6. For choice questions: `Skill(skill="choice-q-create")` → `Skill(skill="choice-q-drill")`

### Startup Order

```
git clone → cd Pass-LLM-with-LLM
  │
  ├── pip install mcp               # optional: for exam-memory MCP server
  │
  ├── edit .mcp.json                # register exam-memory (see docs/mcp-setup-guide.md)
  │
  ├── open in Claude Code
  │     │
  │     ├── first time → say "init" → init-guide auto-configures everything
  │     │     (HANDOFF.md, sources/, AGENTS.md, user profile)
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

### MemPalace Enhancement (Optional)

[MemPalace](https://github.com/MemPalace/mempalace) provides structured knowledge storage with cross-wing knowledge graphs. Best suited for long-term knowledge management beyond a single exam cycle:

| Use Case | How It Helps |
|----------|-------------|
| Knowledge graph | Map prerequisite relationships (e.g., DP ← knapsack, binary search ← sorted array) for targeted review |
| Agent diary | Record learning observations per session; build a searchable history of "what I learned" |
| Cross-project knowledge | Link exam prep notes with project work, interview prep, or research notes |

Best paired with review-tracker (knowledge graph for coverage gaps) and exam-assistant (structured retrieval of prior insights). Not directly called by any bundled skill — use MemPalace tools manually via Claude Code.

### OneFind Enhancement (Optional)

[OneFind](https://github.com/iawnfoanaowt/OneFind) retrieves content from your local knowledge base (Obsidian vaults, Zotero libraries, folders). Useful if you already maintain study notes outside this project:

| Use Case | How It Helps |
|----------|-------------|
| Obsidian notes | Search your existing ML/algorithm notes for related concepts when practicing |
| Zotero library | Retrieve reference papers for Transformer, GNN, Diffusion topics in `llm/` cheatsheets |
| Hybrid search | Combine lexical + semantic search across all local sources |

Best paired with choice-q-create (search notes for question material), exam-assistant (retrieve references during explanation), and review-tracker (check if your notes cover the required topics). Not directly called by any bundled skill — use OneFind tools manually via Claude Code.

#### OneFind + exam-memory: Complementary Search Layers

OneFind's **folder source** can index `exam_memory/experiences/` for semantic search. However, OneFind is designed as a **read-only retrieval** layer — it cannot replace exam-memory's write-through pipeline (save experience → vectorize → store atomically). The recommended setup:

| Layer | Role | Write | Read |
|-------|------|:-----:|:----:|
| `exam-memory` MCP | Experience CRUD + error counting + user profiling | Yes (save, update) | Yes (list, filter by type) |
| OneFind folder source | Semantic search overlay on experience files | No (index refresh only) | Yes (semantic + keyword) |

**Setup**: Configure OneFind's `folder_library` to point at `exam_memory/experiences/`, then use `onefind_search` with `target="folder"` for semantic retrieval of past experiences. After saving new experiences via MCP, trigger `onefind_index_refresh` to pick up changes.

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
| 1 | Experience auto-vectorization → numpy store | `sentence-transformers` (bge-m3) |
| 2 | `list_experiences` supports semantic retrieval | Phase 1 |
| 3 | LLM auto-infers user profile | LLM API |
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
Pass-LLM-with-LLM/
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
