# Orin Collaboration Log

Tracks how well delegating small coding subtasks to Orin (Jetson AGX Orin,
`qwen3-coder-next-128kctx` via Ollama, see global memory
`project_infrastructure`) works for this project, so the workflow can be
judged round over round instead of re-litigated from memory each time.
Same pattern as `invoice_scanner/docs/orin-collaboration-log.md`.

**Columns:** Orin tokens (from the API response's `usage`/`eval_count`
fields), correction tokens (Claude's estimated spend reviewing/fixing
Orin's output), wall-clock time, Sonnet-subagent estimate (rough guess of
what a hosted-model subagent would have cost for the same task, for
comparison).

## 2026-07-15 — mechanical try/except hardening in config.py

During a quick code review (Sonnet fixed the flagged MIDI-notes bug
directly; two Fable5 background agents reviewed the rest of the
codebase), both review agents independently converged on the same
finding: `load_config`/`load_fixtures`/`load_setups` in `config.py` only
caught `FileNotFoundError`, not malformed-file errors
(`yaml.YAMLError` / `json.JSONDecodeError`) — a corrupt config/fixtures/
setups file would crash the app at startup. One agent had already fixed
`load_config`'s `None`-on-empty-file case; the remaining 3-file exception
handling was flagged as "same mechanical fix repeated" rather than fixed
inline, since it was genuinely repetitive text-pattern work.

Delegated to Orin: gave it the full current `config.py` content plus an
exact instruction of what exception types to add and where, asked for
the complete file back, no discussion. First try was correct — only diff
was the three intended except-clause changes (Orin's output also dropped
the file's trailing newline, which Claude restored).

| Task | Orin tokens (prompt+completion) | Correction tokens (est.) | Time | Sonnet-subagent estimate |
|---|---|---|---|---|
| Add YAMLError/JSONDecodeError handling to 3 functions in config.py | 726 + 569 = 1,295 | near-zero — one `printf` to restore a trailing newline | ~71s (mostly Orin inference) | ~1,500-2,500 tokens (read file, edit, verify) for a task this small — Orin was cheaper but not by a large margin here, since the task was already tiny |

**Qualitative takeaway:** "whole file + a precise, itemized instruction,
ask for the full file back" continues to work first-try for small
mechanical patches (consistent with the invoice_scanner log's finding).
For a task this small the win is more about not spending any hosted-model
tokens at all than about wall-clock time — Orin's 71s inference is
slower than a subagent would likely take, but it's free.
