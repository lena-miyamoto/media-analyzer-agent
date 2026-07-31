---
name: media-db
description: >
  Access the media-db archive — search, query, archive, validate, or bootstrap.
  Every read and write to the local archive must go through this skill. Never
  touch media-db/ files directly.
user-invocable: false
---

# media-db

Source of truth for `media-db`. Archive access rules, command contract, bootstrap, command reference.

## When to Use

Any read/write to `./media-db/`: check archived, search keyword/topic/ID, read metadata, list contents,
archive by ID or search query, integrity checks.

Delegated by summarize-article/book/video skills and media-analyzer agent.

## Black-Box Rule

- **Never touch `./media-db/` files directly.** No `cat`, `head`, `tail`, `jq`, `grep`, `sed`, `awk`,
  `python3 -c`, `python3`, `node -e`, or any ad-hoc snippet.
- Black box: **every read** → `uv run media-db-query ...` or `uv run media-db-lookup ...`.
  **Every write** → `uv run media-db ...`. Zero exceptions.
- No `python`, `python3`, direct paths, absolute paths, shebangs. Only `uv run ...` from repo root.
- **If `uv run` tools don't support a query pattern, report it — don't work around with inline code.**

### Forbidden Patterns

| Forbidden | Why | Use Instead |
|---|---|---|
| `python3 -c "import json; ..."` reading `index.json` | Bypasses validation | `uv run media-db-query --search-keyword "..."` |
| `python3 -c "..."` for any media-db op | No integrity checks | `uv run media-db-lookup --id ...` |
| `jq` / `cat` / `grep` on `media-db/index.json` | Bypasses tool layer | `uv run media-db-query --list-topics` |
| `python3` or `python` in any form | Forbidden by AGENTS.md contract | `uv run <entry-point>` |
| `node -e`, `perl -e` touching media-db files | Same bypass, different language | `uv run media-db-*` tools |

## Bootstrap

- `./media-db/` gitignored. Never create by hand — tooling auto-creates tree and `index.json`.
- Bootstrap fresh checkout: `uv run media-db --sync-index`. Creates dir tree and empty `index.json`.
- Archive first item: run any archival command.
- Verify: `uv run media-db-integrity-check --media-db media-db`. Empty archive passes if dirs + `index.json` exist.
- Query/lookup tools read-only. Missing `media-db/` → run archival command first.

## Source Policies

Consult before archiving, querying, or analyzing:

| Domain | Reference |
|--------|-----------|
| Full command parameter reference | `.claude/agents/resources/media-db-commands.md` |
| Archive layout, naming, frontmatter | `.claude/reference/media-db-structure.md` |
| AGENTS.md source priority, tool preferences | `AGENTS.md` |
| Script development conventions | `.claude/scripts/DEVELOPER.md` |

## Archival Conventions

- Always `--topic <name>` on archival (human-readable, e.g. `climate-science`). Slug auto-derived.
- `--topic-slug` only when auto-derivation fails.
- Integrity check auto-runs after every archival. Errors block — fix immediately.

## During-Analysis Use

During live analysis: only **read-only, local, no-network** commands:

| Permitted during analysis | Between-analysis only |
|---|---|
| `uv run media-db-query --search-keyword "..."` | `uv run media-db --id ...` (writes) |
| `uv run media-db-query --list-topics` | `uv run media-db --source ... --query "..."` (network) |
| `uv run media-db-query --read-metadata "..."` | `uv run media-db-integrity-check` (waste mid-analysis) |
| `uv run media-db-lookup --id ...` | `WebSearch`, `WebFetch` for new content (network) |

Read-only: sub-second, local. Archival: between-analysis.

## Command Reference

All scripts via `uv run` from repo root. Default JSON; `--format text` for readable.
Full reference: `.claude/agents/resources/media-db-commands.md`. Quick reference below.

### Archive (`media-db`)

| Operation | Command |
|-----------|---------|
| By PMID | `uv run media-db --pmid <PMID> --topic '<name>'` |
| By EPMC record | `uv run media-db --source europe-pmc --epmc-record <SOURCE:ID> --topic '<name>'` |
| By DOI | `uv run media-db --doi <DOI> --topic '<name>'` |
| Search | `uv run media-db --source <SOURCE> --query '<query>' --topic '<name>'` |
| Archive first N | `uv run media-db --source <SOURCE> --query '<query>' --archive-first <N> --topic '<name>'` |
| Multiple IDs | `uv run media-db --pmid <ID1> --pmid <ID2> --topic '<name>'` |
| From lookup | `uv run media-db-lookup --pmid <ID> \| uv run media-db --from-lookup --topic '<name>'` |
| Sync index | `uv run media-db --sync-index` |
| Label entry | `uv run media-db --label '<label>' --path <PATH>` |

### Query (`media-db-query`)

| Operation | Command |
|-----------|---------|
| List topics | `uv run media-db-query --list-topics` |
| List items/topic | `uv run media-db-query --topic '<slug>'` |
| Check ID | `uv run media-db-query --check-id '<ID>'` |
| Read metadata | `uv run media-db-query --read-metadata '<path>'` |
| Keyword search | `uv run media-db-query --search-keyword '<term>'` |
| Scoped keyword | `uv run media-db-query --search-keyword '<term>' --search-topic '<slug>'` |
| Recent items | `uv run media-db-query --recent <N>` |

### External Lookup (`media-db-lookup`)

| Operation | Command |
|-----------|---------|
| Lookup by ID | `uv run media-db-lookup --id <ID>` |
| Lookup by DOI | `uv run media-db-lookup --doi <DOI>` |

### Maintenance

| Operation | Command |
|-----------|---------|
| Integrity check | `uv run media-db-integrity-check --media-db media-db` |
| JSON integrity | `uv run media-db-integrity-check --media-db media-db --json` |
| All tests | `uv run test` |

### Lint Rules

- After `*.md` edits: `uv run lint-md` (or `--fix`).
- **Never `uv run pymarkdownlnt` directly.** Only `uv run lint-md`.
- After `*.py` edits: `uv run test`. Full suite must pass.
