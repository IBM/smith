# Smith — agent guidance

Project guidance lives in **[`/CLAUDE.md`](../CLAUDE.md)** at the repository root —
read it first. It is the single source of truth for what Smith is, the
skill/CLI architecture, the configuration model, the data flow, and the hard
rules for editing `assets/policy.rego`.

This file exists so that agents which look for guidance under `.claude/` are
pointed at the root document rather than working without context. Keep
project-wide instructions in `/CLAUDE.md`; do not duplicate them here.

Local, machine-specific Claude Code settings (`.claude/settings.local.json`) are
intentionally git-ignored.
