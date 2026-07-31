# CLAUDE.md

General-purpose media analysis workspace. Summarize, analyze, and extract structured information from books, articles, videos, transcripts, and other media.

## Shared

- Make the smallest local change that works. If patch context is stale, re-read and retry. Scratch files are ephemeral unless asked otherwise.
- Shared skill procedure lives in `.claude/skills/<name>/SKILL.md`; `.github/skills` are thin wrappers only.
- For CSV/TSV work, check `command -v mlr csvcut csvlook csvstat csvjson`; prefer `mlr`; do not assume a `csvkit` binary exists.
- For local HTML sources, prefer `html2text -utf8 -width 100 -nobs <file>` for readable text; do not require redundant browser dump tools like `lynx`, `w3m`, or `elinks`.
- For summaries and research write-ups, use only the provided source text. Do not add author biography, other works, historical context, later interpretations, common critiques, comparisons, evaluation, or school-specific frames unless the user explicitly asks for them. If the text is ambiguous, report the ambiguity rather than resolving it externally.
- Tie every claim to specific passages in the source material. After drafting, self-audit for reliance on information outside the source and revise anything flagged.
- Re-read the table or source file before each edit, trust file state over memory, validate immediately, and prefer table-aware checks.
- Ignore validation noise from intentionally empty optional fields.
- Use standard German orthography (umlauts, `ß`) unless the user asks for ASCII or a technical constraint requires it.
- Instruction files in this repo must not cite a generated, ignored, or archive output path as a template, exemplar, source of truth, or reusable pattern. Such paths may be documented only as output locations, path schemas, or concrete examples of where newly generated material should be written.
- `compress-skill` compresses instruction `.md` files in place to cut token cost while keeping meaning exact. Invoke after editing any instruction file in this repo, or when explicitly asked.

## Source Priority

**General facts** — Wikipedia is the primary source of truth. Prefer the German Wikipedia (`de.wikipedia.org`) for topics with regional German-language relevance; use English Wikipedia (`en.wikipedia.org`) for broader international topics and as a fallback. Cross-check between the two language editions when precision matters.

Cite sources explicitly. For Wikipedia: article title, language edition, and permalink or revision date.

## No Local Archive

This workspace does not maintain a local database or archive. Work from user-provided sources: attached files, URLs, transcripts, or pasted text. Do not create a persistent archive directory unless the user explicitly requests one.

## Scratch Outputs

- Write derived outputs to `tmp/` (or a user-specified path).
- Keep scratch CSVs aligned with source text unless the user asks for a rewrite.
- After table edits, run the narrowest relevant validation for that slice.

## Architecture

Context engineering: `.claude/skills/optimize-repo/rules/context-engineering-best-practices.md` — authoritative standard for all instruction files in this repo.
Skills: `.claude/skills/<name>/SKILL.md` owns procedure; `.github/skills` are thin wrappers pointing to `.claude/`.
Agents: `.claude/agents/<name>.md` owns behavior; `.github/agents` are thin wrappers pointing to `.claude/`.
`.claude/` is the sole source of truth. No separate `.agents/` directory.

## Harness Entrypoints

- `CLAUDE.md` — Claude Code routing (this file)
- `.github/copilot-instructions.md` — GitHub Copilot routing
- `.github/agents/media-analyzer.agent.md` — Copilot agent
- `.claude/agents/media-analyzer.md` — Claude Code agent
- `.claude/skills/<name>/SKILL.md` — Skill procedures (source of truth)
- `.github/skills/<name>/SKILL.md` — Copilot skill wrappers
