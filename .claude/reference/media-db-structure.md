# Archive Structure

media-db layout, naming, frontmatter, and quality rules. Reference this file — don't duplicate.

## Directory layout and naming

- Lowercase kebab-case folder and file names.
- Required top-level categories:
  - `searches/<topic-slug>/` — machine-readable search JSON (PubMed esearch or Europe PMC search format).
  - `papers/<topic-slug>/<identifier>-<title-slug>/` — paper metadata + abstract. Folder pattern:
    `pmid-<N>-<title-slug>` for PubMed, `epmc-<source>-<id>-<title-slug>` for Europe PMC.
  - `fulltext/<topic-slug>/<identifier>-<title-slug>/` — full-text source markdown with YAML frontmatter
    plus `metadata.json` sidecar.
  - `guidelines/<topic-slug>/<title-slug>/` — guideline source markdown. One file per language:
    `source.md` (default) or `source.<lang>.md` (e.g. `source.de.md`).
  - `web/<topic-slug>/` — archived web pages or reproducible search definitions as `.html` files.

## Paper standard (mandatory)

Every paper directory must contain:
- `metadata.json` — PubMed esummary or Europe PMC search format, exactly as returned by the API.
- `abstract.txt` — plain text abstract.

Identifier from folder name, not metadata. Folder-name PMID/EPMC ID must match metadata (checked by
integrity validator).

## YAML frontmatter (guidelines and fulltext)

Every `source.md` or `source.<lang>.md` must open with YAML frontmatter containing at minimum:
`title`, `authors`, `source`, `source_url`, `access_date` (YYYY-MM-DD), `language` (language of text
in that file), `extraction_notes` (how obtained and processed).

## Source priority

Paper metadata resolution, preferred order:
1. `index.json` (cached metadata)
2. `searches/<topic>/` (search result JSON)
3. Fetch from PubMed / Europe PMC (authoritative)

## index.json

Master index at `media-db/index.json`: five arrays — `searches`, `papers`, `fulltext`, `guidelines`,
`web`. Each entry: `path` key relative to `media-db/` plus source-specific fields.
Regenerate: `uv run media-db --sync-index`.

## Black-box access rule

Never touch `media-db/` files directly. Reads: `uv run media-db-query` or `uv run media-db-lookup`.
Writes: `uv run media-db`. No inline Python, no `jq`/`grep`/`cat` on media-db files.
