# AGENTS.md

## Project Contract

This repository is an **execution harness** for AI / algorithm written-exam preparation. It is not a general knowledge base and not a place for broad research unless the user explicitly asks.

Primary goal: maximize written-exam pass probability. Secondary goal: keep only the minimum useful interview-prep material for follow-up interviews.

Default focus can be adjusted per target, but the baseline is:

| Area | Default |
|------|---------|
| Question types | Single choice, multi-select, programming |
| Math | Linear algebra, probability, calculus quick-score questions |
| AI focus | Transformer, GNN, diffusion models, LLM inference optimization |
| Common overlap | SFT / LoRA / RLHF, RAG, KV cache, Python OJ algorithms |

When tradeoffs appear, prioritize algorithm AC practice, then math / multiple-choice quick-score topics, then AI concept review, then project-expression polishing.

## Harness Engineering Rules

Every session must preserve the minimum loop:

```text
intake -> practice -> record -> review -> handoff
```

Keep files in their lane:

| Need | Source of Truth |
|------|-----------------|
| Session bootstrap | `START_HERE.md` |
| Current target, last work, next action | `HANDOFF.md` |
| User-facing setup and directory guide | `README.md` |
| Detailed skill behavior | `skills/` |
| Target-specific practice state | `targets/{target}/` |
| Shared daily logs and optional MCP source | `shared/` |
| Dev-only plans, roadmap, branch governance | `docs/` |

Do not turn `AGENTS.md` into an architecture manual. Put durable explanations in README / docs, and put operational details in the relevant skill file.

## Runtime Modes

The harness must continue even when enhanced tooling is unavailable.

| Mode | Condition | Persistence |
|------|-----------|-------------|
| Full MCP Mode | `exam-memory` MCP is callable and the repo is writable | Markdown + MCP dual write |
| Local Markdown Mode | MCP / ChatMem / local indexes are unavailable but repo files are writable | `HANDOFF.md`, daily logs, `mistake_log.md`, round files |
| Stateless Lite Mode | repo is not writable, key files are missing, or the session can only continue in chat | return append blocks such as `[MISTAKE_LOG_APPEND]`, `[DAILY_PROBLEM_LOG_APPEND]`, `[CHOICE_ROUND_SUMMARY]`, `[HANDOFF_UPDATE]` |

MCP, ChatMem, local indexes, review CLI, web search, and interactive quiz tools are enhancements. If they fail, skip them quietly inside the workflow and continue the learning loop. The final report must say what degraded and what Markdown blocks need to be saved.

When calling project MCP tools, use full tool names such as `mcp__exam-memory__list_experiences`. Do not block practice on MCP retries, and do not expose MCP internals unless the user is debugging tooling.

## Session Start

1. If `HANDOFF.md` still contains template placeholders, invoke `init-guide` when the user says `init`, `初始化`, `第一次用`, or asks to change exam target.
2. Read `START_HERE.md`.
3. Read `HANDOFF.md`.
4. Open today's `shared/daily/YYYY-MM-DD.md`; if missing and writable, create it from the local pattern, otherwise return a `[DAILY_PROBLEM_LOG_APPEND]` block.
5. Check the active target's `mistake_log.md`, `mock_exam_log.md`, and task board when they exist.
6. Use `review-tracker` when the user asks for progress, today's plan, weak spots, or readiness.

## Skill Routing

Use the smallest skill path that keeps the loop moving.

| User intent | Required path |
|-------------|---------------|
| Start any OJ / ACM problem | `solve-skeleton` first |
| Diagnose WA / TLE / wrong logic | `solve-analyze`, then record the root cause |
| Annotate a working solution | `algo-annotation` |
| Generate choice or multi-select practice | `choice-q-create` |
| Run choice-question practice | `choice-q-drill` |
| Ask for progress / weak topics / today plan | `review-tracker` |
| General exam help with local memory when useful | `exam-assistant` |
| First-run target configuration | `init-guide` |

OJ pipeline:

```text
solve-skeleton -> fill solve() -> test -> solve-analyze if WA/TLE/uncertain -> algo-annotation -> log
```

Choice-question pipeline:

```text
choice-q-create -> choice-q-drill -> mistake_log / round summary -> next drill
```

If the user mentions previous context, project history, recall, continuation, migration, handoff, `记得`, `之前`, `继续`, or `交接`, use ChatMem if available. Treat indexed local-history hits as evidence, not approved startup rules; ask before expanding old conversations.

## Recording Rules

For every algorithm problem:

- Record result in today's `shared/daily/YYYY-MM-DD.md` Problem Log.
- If WA / TLE / stuck, append topic, root cause, fix, and retry note to `targets/{target}/mistake_log.md`.
- If timed practice, update `targets/{target}/mock_exam_log.md` with problem count, solved count, stuck points, and next fixes.

For choice-question drills:

- Save round summaries under `targets/{target}/progress/choice-questions/` when writable.
- Record wrong concepts in `targets/{target}/mistake_log.md`.
- If persistence is unavailable, return `[CHOICE_ROUND_SUMMARY]`, `[MISTAKE_LOG_APPEND]`, `[DAILY_PROBLEM_LOG_APPEND]`, and `[HANDOFF_UPDATE]`.

Before ending a session, update `HANDOFF.md` with completed work, evidence used, algorithm results, review results, next concrete task, and blockers.

## Practice Rules

- Prefer Python 3, stdin / stdout, ACM-style templates, and simple readable solutions.
- Write the brute-force idea briefly before optimizing.
- If stuck for 20 minutes, inspect a hint or editorial, then re-code from memory.
- If a solution passes, still write one sentence about the invariant or trick.
- Prioritize hash / sort, binary search, prefix sum, sliding window, greedy, BFS / DFS, heap, and simple DP.
- Avoid advanced topics unless repeated mocks show they are necessary.
- For LLM review, keep to high-yield written-exam topics: Transformer / attention, SFT, LoRA, QLoRA, RLHF, DPO, RAG, Agent, KV cache, inference optimization, evaluation, hallucination control, LLaMA3 details, GNN basics, diffusion basics, and math quick-review.
- The LoRA / SFT mini-project is optional proof of hands-on ability. If local GPU or environment setup is not smooth within 1 hour, use Colab or convert it into an interview-ready plan.

## Operating Rules

- Answer and write task notes in Chinese unless the user asks otherwise.
- Keep edits scoped to this repository unless the user explicitly asks otherwise.
- Do not spend a session on broad public-source research unless explicitly requested.
- Do not overfit to one company's rumored problem list; practice transferable OJ patterns.
- Do not spend more than 1 hour blocked on deployment, CUDA, local fine-tuning, or cloud setup.
- Preserve user changes. Do not revert unrelated edits.

## Branch Boundary

`docs/**`, `skills/branch-ops.md`, `skills/dev-review-flow/**`, `skills/harness-dev-flow/**`, and `prompts/review-fix-session-prompt.md` are dev-only governance content. They may be tracked on `dev`, but must not enter `main`.

`.gitignore` is only the first guardrail. Main extraction must still check staged-file allowlists / denylists.

When a referenced dev-only doc or skill file is ignored by `.gitignore`, force-add only the exact intended path on `dev`:

```bash
git add -f -- docs/path/to/file.md
```

Never use `git add -f .`, and never force-add dev-only material on `main` or during main extraction.

## Where Details Live

| Topic | Read |
|-------|------|
| Startup sequence and manual fallback | `START_HERE.md` |
| Public user guide and MCP setup | `README.md` |
| Current dev roadmap and docs status | `docs/INDEX.md`, `docs/dev-roadmap.md` |
| Main / dev extraction rules | `docs/branch-workflow.md` |
| Skill-specific behavior | relevant file under `skills/` |
