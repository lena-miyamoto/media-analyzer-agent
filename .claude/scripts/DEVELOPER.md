---
description: >
  Internal media-db directory structure and conventions. Only relevant when extending the script stack
  in .claude/scripts/ — never when using uv run entry points.
---

# media-db Developer Notes

Directory structure and conventions. **Only relevant when extending the media-db script stack.**
Agents and skills must never touch `media-db/` directly — all access via `uv run` entry points in
`../agents/resources/media-db-commands.md`.

## Directory Structure (`./media-db/`)

Lowercase kebab-case. `./media-db/index.json` mandatory — every entry listed. Update on every new
or moved archive.

Required top-level categories:

- `searches/<topic-slug>/` — machine-readable JSON (`uncategorized/` when no topic).
- `papers/<topic-slug>/<identifier>-<title-slug>/` — `metadata.json` + `abstract.txt`. Never split.
- `fulltext/<topic-slug>/<identifier>-<title-slug>/` — `source.md` with YAML frontmatter + `metadata.json`.
- `guidelines/<topic-slug>/<title-slug>/` — `source.<lang>.md` with YAML frontmatter.
- `web/<topic-slug>/` — archived web pages or reproducible search definitions.

## Conventions

- **Paper standard:** `papers/`: `metadata.json` + `abstract.txt`. `fulltext/`: `source.md` + `metadata.json`.
  No intermediate artifacts.
- **YAML frontmatter** on every source file: `title`, `authors`, `source`, `source_url`, `access_date`
  (YYYY-MM-DD), `language`, `extraction_notes`.
- **Source priority:** `index.json` → `searches/` → fetch.
