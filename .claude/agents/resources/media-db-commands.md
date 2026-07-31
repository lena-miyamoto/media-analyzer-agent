# media-db Command Reference

Every command: `uv run <entry-point> …` from repo root. Default output JSON unless noted; use
`--format text` for human-readable where supported.

`python3`, `python`, any direct Python invocation **forbidden**. All access via `uv run` entry points
so validation, indexing, integrity checks always applied.

Archive sources: PubMed (E-utilities), Europe PMC (REST API), web discovery (Google Scholar, DOAJ,
Open Science Directory). Archive ops always require `--topic`.

External lookups: PMID via PubMed E-utilities, Europe PMC record via REST API, DOI resolution
(Pubmed first, Europe PMC fallback).

Integrity: `uv run media-db-integrity-check` auto-runs after every archival. Errors block completion
(exit 1). Fix immediately.

---

## `uv run media-db` — Archival

Archives literature searches, paper records (PMID, Europe PMC SOURCE:ID, DOI), and web discovery
queries into `media-db/`. Mutually exclusive sourcing: `--query`, `--pmid`/`--epmc-record`/`--doi`,
or `--from-lookup` (read JSON from stdin).

| Parameter | Type | Default | Description |
|---|---|---|---|
| `--source` | choice | `pubmed` | Primary source: `pubmed`, `europe-pmc`, `google-scholar`, `doaj`, or `open-science-directory` |
| `--query` | str | — | Search query to archive for the selected source |
| `--search-slug` | str | — | Optional slug for the saved search file |
| `--topic` | str | `uncategorized` | Medical topic for grouping output (e.g. `endometriosis`, `weight-loss`, `adhd`) |
| `--topic-slug` | str | — | Explicit kebab-case slug for the topic folder. Overrides `--topic` if both given |
| `--pmid` | str[] | `[]` | PMID to archive. Repeatable (`--pmid 12345678 --pmid 87654321`) |
| `--epmc-record` | str[] | `[]` | Europe PMC record as `SOURCE:ID`. Repeatable |
| `--doi` | str[] | `[]` | DOI to resolve and archive. Repeatable. Tries PubMed first, then Europe PMC |
| `--archive-first` | int | `0` | Also archive the first N PMIDs/records returned by `--query` |
| `--retmax` | int | `20` | How many machine-readable hits to request for the archived search JSON |
| `--media-db` | str | `media-db` | Target `media-db/` directory path |
| `--email` | str | — | Optional contact email passed to NCBI E-utilities |
| `--delay` | float | `0.34` | Delay between ID fetches in seconds |
| `--sync-index` | flag | off | Regenerate `index.json` from the filesystem without fetching anything |
| `--label` | str | — | Set a label on an existing archive entry (requires `--path`) |
| `--path` | str | — | Path of the archive entry to label (e.g. `papers/endometriosis/pmid-12345678-title-slug`) |
| `--from-lookup` | flag | off | Read JSON from stdin (e.g. output of `media-db-lookup`) and extract PMIDs/EPMC records for archival |
| `--migrate` | flag | off | Migrate existing flat `media-db/` structure to topic-based per-paper folders. Preserves originals |
| `--migrate-dry-run` | flag | off | Preview `--migrate` without copying files |

---

## `uv run media-db-query` — Local Archive Query (read-only)

Queries local `media-db/` archive. Exactly one operation flag required from mutually exclusive group.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `--media-db` | str | `media-db` | Path to `media-db/` root directory |
| `--format` | choice | `json` | Output format: `json` or `text` |

**Operation (mutually exclusive — pick exactly one):**

| Flag | Type | Description |
|---|---|---|
| `--list-topics` | flag | List all topics with paper and search counts |
| `--topic` | str | List all papers in a topic folder |
| `--check-pmid` | str | Check if a PMID is already archived |
| `--check-epmc` | str | Check if a Europe PMC record is archived (format: `SOURCE:ID`) |
| `--pmids-from-search` | str | Extract PMID list from an archived search JSON file |
| `--read-metadata` | str | Read metadata from an archived paper directory path |
| `--search-keyword` | str | Search all archived papers by keyword (case-insensitive, titles and abstracts) |
| `--recent` | int | Return N most recently added papers |
| `--search-searches` | str | Keyword search within archived search JSON query fields |

**Modifiers (usable with certain operations):**

| Parameter | Type | Default | Applies to | Description |
|---|---|---|---|---|
| `--search-topic` | str | — | `--search-keyword`, `--search-searches` | Restrict search to a topic folder |
| `--show-abstract` | flag | off | `--read-metadata` | Also include the abstract text |
| `--summary` | flag | off | `--read-metadata` | Output a compact summary instead of full metadata |

---

## `uv run media-db-lookup` — External Lookup (read-only, no archival)

Fetches structured paper data (title, abstract, authors, DOI) by PMID, Europe PMC SOURCE:ID, or DOI.
Does NOT archive. Returns JSON to stdout. At least one identifier required.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `--pmid` | str[] | `[]` | PMID to look up. Repeatable |
| `--epmc-record` | str[] | `[]` | Europe PMC record as `SOURCE:ID`. Repeatable |
| `--doi` | str[] | `[]` | DOI to resolve. Tries PubMed first, then Europe PMC |
| `--format` | choice | `json` | Output format: `json` or `text` |
| `--email` | str | — | Optional contact email passed to NCBI E-utilities |
| `--delay` | float | `0.34` | Delay between fetches in seconds |

---

## `uv run media-db-integrity-check` — Validation

Structural and data integrity checks on a `media-db/` archive. Auto-runs after archival.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `--media-db` | str | `media-db` | Target `media-db/` directory path |
| `--json` | flag | off | Emit findings as machine-parseable JSON instead of human-readable text |

---

## `uv run lint-md` — Markdown Linting

Runs `pymarkdownlnt` on repo markdown files. Default: `AGENTS.md`, `README.md`, `CLAUDE.md`,
`.github/`, `.claude/`.

| Parameter | Type | Default | Description |
|---|---|---|---|
| *(none)* | — | — | Scan default paths (`AGENTS.md`, `README.md`, `CLAUDE.md`, `.github`, `.claude`) |
| `--fix` | flag | off | Auto-fix violations where possible, then scan remaining issues |

---

## `uv run test` — Test Suite

Runs pytest on `tests/` with `-v` (verbose) by default.

| Parameter | Type | Default | Description |
|---|---|---|---|
| *(none)* | — | — | Run `pytest tests/ -v` |
| *(any pytest args)* | — | — | Arguments are forwarded directly to pytest |
