# media-analyzer-agent

Reusable agent config for general-purpose media analysis, summarization, and information extraction.

Not an application or library. A workspace for:

- shared GitHub Copilot and Claude Code customization files
- source-backed summarization workflows for books, articles, videos, and transcripts
- structured information extraction from media content
- scratch outputs under `tmp/`

## Tool Surfaces

Shared skill instructions live under `.agents/skills/`. Files under `.github/skills/` and `.claude/skills/` are thin discovery wrappers.

### GitHub Copilot

- `media-analyzer`: general-purpose media analysis — summarization, information extraction, content analysis
- `optimize-repo`: maintain repo's cross-harness conventions

Shared rules: [AGENTS.md](./AGENTS.md). Copilot-specific routing: [.github/copilot-instructions.md](./.github/copilot-instructions.md).

### Claude Code

Claude exposes the same surfaces through `.claude/agents/` and `.claude/skills/`. Routing: [CLAUDE.md](./CLAUDE.md).

## Recommended Tooling

Media analysis workflows work best with:

- `mlr` (Miller) — inspect and transform CSV/TSV; prefer first
- `csvcut`, `csvlook`, `csvstat`, `csvjson` from `csvkit` (no top-level `csvkit` binary)
- `yt-dlp` — fetch subtitle tracks from video URLs
- `html2text` — Python script for converting HTML source pages into readable text
- Python 3 for installing `csvkit` and `html2text`

## Install On Linux

### Debian or Ubuntu

```bash
sudo apt install -y miller csvkit html2text yt-dlp
```

### Fedora

```bash
sudo dnf install -y miller python3-csvkit python3-html2text yt-dlp
```

### Arch Linux

```bash
sudo pacman -S --needed miller csvkit html2text yt-dlp
```

## Install On macOS

```bash
brew install miller csvkit html2text yt-dlp
```

## Install On Windows

PowerShell with `winget`:

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id JohnKerl.Miller

py -m pip install --user csvkit
py -m pip install --user yt-dlp
py -m pip install --user html2text
```

Reopen PowerShell after installing Python if `py` is not yet on PATH.

## Working In This Repo

No build step. Use the surfaces listed above; follow [AGENTS.md](./AGENTS.md) for analysis, source, and validation rules.

This workspace does not maintain a local archive or database. Work from user-provided sources: attached files, URLs, transcripts, or pasted text.

## Source Priority

- **General facts** — Wikipedia is the primary source of truth. German Wikipedia (`de.wikipedia.org`) for regional German-language relevance; English Wikipedia (`en.wikipedia.org`) for broader international topics.
- **Medicine and heavy science** — when the topic goes beyond general knowledge, scientific paper databases replace Wikipedia: PubMed, Europe PMC, Google Scholar, DOAJ, Trip Database, OpenMD, and Free Medical Journals. Prefer systematic reviews and meta-analyses.

Full source rules in [AGENTS.md](./AGENTS.md).
