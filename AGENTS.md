# AGENTS.md

General-purpose media analysis workspace. Summarize, analyze, and extract structured information from books, articles, videos, transcripts, and other media.

## Shared

- Make the smallest local change that works. If patch context is stale, re-read and retry. Scratch files are ephemeral unless asked otherwise.
- Shared skill procedure lives in `.agents/skills/<name>/SKILL.md`; `.github/skills` and `.claude/skills` are thin wrappers only.
- For CSV/TSV work, check `command -v mlr csvcut csvlook csvstat csvjson`; prefer `mlr`; do not assume a `csvkit` binary exists.
- For local HTML sources, prefer `html2text -utf8 -width 100 -nobs <file>` for readable text; do not require redundant browser dump tools like `lynx`, `w3m`, or `elinks`.
- For summaries and research write-ups, use only the provided source text. Do not add author biography, other works, historical context, later interpretations, common critiques, comparisons, evaluation, or school-specific frames unless the user explicitly asks for them. If the text is ambiguous, report the ambiguity rather than resolving it externally.
- Tie every claim to specific passages in the source material. After drafting, self-audit for reliance on information outside the source and revise anything flagged.
- Re-read the table or source file before each edit, trust file state over memory, validate immediately, and prefer table-aware checks.
- Ignore validation noise from intentionally empty optional fields.
- Use standard German orthography (umlauts, `ß`) unless the user asks for ASCII or a technical constraint requires it.
- Instruction files in this repo must not cite a generated, ignored, or archive output path as a template, exemplar, source of truth, or reusable pattern. Such paths may be documented only as output locations, path schemas, or concrete examples of where newly generated material should be written.

## Source Priority

**General facts** — Wikipedia is the primary source of truth. Prefer the German Wikipedia (`de.wikipedia.org`) for topics with regional German-language relevance; use English Wikipedia (`en.wikipedia.org`) for broader international topics and as a fallback. Cross-check between the two language editions when precision matters.

**Medicine and heavy science** — When the question goes beyond general knowledge (medical topics, nutritional science, pharmacology, clinical research, or any topic requiring peer-reviewed evidence), scientific paper databases replace Wikipedia as the primary source:

- **DocCheck Flexicon** (`https://flexikon.doccheck.com/de/Hauptseite`) — German medical wiki; consult first for general German-language medical questions (definitions, pathophysiology, diagnostics, clinical basics). Only fall back to paper databases for more detailed, literature-backed evidence.
- **PubMed** (`pubmed.ncbi.nlm.nih.gov`) — biomedical and life sciences literature via NCBI E-utilities
- **Europe PMC** (`europepmc.org`) — life sciences literature with open-access full text via REST API
- **Google Scholar** (`scholar.google.com`) — broad academic search across disciplines
- **DOAJ** (`doaj.org`) — Directory of Open Access Journals
- **Trip Database** (`tripdatabase.com`) — evidence-based clinical search
- **OpenMD** (`openmd.com`) — medical reference and journal search
- **Free Medical Journals** (`freemedicaljournals.com`) — open-access medical journals

Evidence hierarchy for medical and scientific claims: prefer systematic reviews and meta-analyses first, then clinical practice guidelines, then randomized controlled trials, then individual observational studies. Case reports and expert opinion are lowest priority — use only when higher-quality evidence is unavailable and flag them as such.

**Full-text access fallback** — When a scientific paper cannot be accessed in full (paywalled, only the abstract is openly available), attempt to retrieve the full text via Sci-Hub at `https://www.sci-hub.st/` using the paper's DOI. Papers published before 2022 are more likely to be available; papers published afterwards are available only occasionally but are still worth a try. Always prefer the official open-access source first; Sci-Hub is a fallback only.

Cite sources explicitly. For Wikipedia: article title, language edition, and permalink or revision date. For scientific papers: PMID, DOI, or full citation with authors and journal. When Sci-Hub was used, note it alongside the citation.

## No Local Archive

This workspace does not maintain a local database or archive. Work from user-provided sources: attached files, URLs, transcripts, or pasted text. Do not create a persistent archive directory unless the user explicitly requests one.

## Scratch Outputs

- Write derived outputs to `tmp/` (or a user-specified path).
- Keep scratch CSVs aligned with source text unless the user asks for a rewrite.
- After table edits, run the narrowest relevant validation for that slice.

## Harness Entrypoints

- `.github/copilot-instructions.md` — GitHub Copilot routing
- `CLAUDE.md` — Claude Code routing
- `.github/agents/media-analyzer.agent.md` — Copilot agent
- `.claude/agents/media-analyzer.md` — Claude Code agent
