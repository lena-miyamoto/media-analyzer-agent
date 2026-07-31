"""Shared utilities for media-db scripts.

Constants, slugify, API fetch helpers, and the unified default_paper_entry
parser used across media-db.py, media-db-lookup.py, media-db-query.py, and
media-db-integrity-check.py.
"""

import html as _html
import json
import re
import sys as _sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Repository paths — canonical single source for all scripts
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MEDIA_DB = REPO_ROOT / "media-db"

# ---------------------------------------------------------------------------
# API / network constants
# ---------------------------------------------------------------------------

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EUROPE_PMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# slugify — canonical version (NFKD → ASCII → kebab-case)
# ---------------------------------------------------------------------------


def slugify(text, fallback="record", max_words=10, max_length=80):
    """Normalise *text* into an ASCII kebab-case slug."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if not text:
        return fallback
    words = [word for word in text.split("-") if word]
    text = "-".join(words[:max_words])
    return text[:max_length].rstrip("-") or fallback


# ---------------------------------------------------------------------------
# Language extraction from archive filenames
# ---------------------------------------------------------------------------

# Known source-file suffixes in extraction order (strip before language detection).
_KNOWN_SOURCE_SUFFIXES = (".md", ".srt", ".vtt", ".auto")


def lang_from_filename(filename):
    """Extract a language code from an archive source filename.

    Handles patterns like ``source.en.md``, ``source.de.auto.md``,
    ``transcript.en.srt``, and bare ``source.md`` (returns ``None``).
    """
    stem = str(filename)
    # Strip known suffixes from right to left until we reach the language segment
    while True:
        stripped = False
        for suffix in _KNOWN_SOURCE_SUFFIXES:
            if stem.endswith(suffix) and stem != suffix:
                stem = stem[: -len(suffix)]
                stripped = True
                break
        if not stripped:
            break

    # After stripping, the last dot-separated segment should be the language code
    if "." in stem:
        candidate = stem.rsplit(".", 1)[-1]
        # Validate it looks like a language code (2-3 lowercase letters)
        if re.match(r"^[a-z]{2,3}$", candidate):
            return candidate
    return None


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------


def save_text(path, content):
    path.write_text(content, encoding="utf-8")


def atomic_write(path, content):
    """Write *content* to *path* atomically via a temporary file + rename.

    On POSIX ``Path.replace`` is atomic when the source and destination are
    on the same filesystem.  This prevents corruption if the process crashes
    mid-write.
    """
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _trash_or_unlink(file_path):
    """Move *file_path* to the desktop trash, falling back to permanent delete.

    Uses ``gio trash`` when available (GNOME/GLib) so deleted files can be
    restored.  Falls back to :func:`os.unlink` when ``gio`` is not on PATH.
    """
    import os
    import subprocess as _subprocess

    path_str = str(file_path)

    # gio trash fails silently if the file doesn't exist, so guard first.
    if not os.path.lexists(path_str):
        return

    try:
        _subprocess.run(
            ["gio", "trash", "-f", path_str],
            capture_output=True,
            timeout=10,
            check=True,
        )
    except (FileNotFoundError, _subprocess.CalledProcessError, OSError):
        os.unlink(path_str)


# ---------------------------------------------------------------------------
# API fetch helpers (raise RuntimeError on failure — callers decide how to
# handle it)
# ---------------------------------------------------------------------------


def _fetch_url(url, label, timeout=60, retries=2, retry_delay=0.25):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                charset = response.headers.get_content_charset("utf-8")
                try:
                    return raw.decode(charset)
                except UnicodeDecodeError:
                    return raw.decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code < 500 or attempt == retries:
                break
        except (urllib.error.URLError, OSError) as exc:
            last_error = exc
            if attempt == retries:
                break
        if retry_delay > 0:
            time.sleep(retry_delay * (2 ** attempt))
    raise RuntimeError(f"error fetching {label}: {last_error}")


def fetch_pubmed(endpoint, params, timeout=60):
    """GET *endpoint* from PubMed E-utilities, return decoded UTF-8 body.

    Raises ``RuntimeError`` on network / HTTP errors so library callers can
    catch and recover (e.g. fall back to an "unavailable" message).
    """
    url = f"{EUTILS_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    return _fetch_url(url, f"PubMed {endpoint}", timeout=timeout)


def fetch_europe_pmc(module, params, timeout=60):
    """GET *module* from Europe PMC REST API, return decoded UTF-8 body.

    Raises ``RuntimeError`` on network / HTTP errors.
    """
    url = f"{EUROPE_PMC_BASE}/{module}?{urllib.parse.urlencode(params)}"
    return _fetch_url(url, f"Europe PMC {module}", timeout=timeout)


# ---------------------------------------------------------------------------
# europe_pmc_article_url
# ---------------------------------------------------------------------------


def europe_pmc_article_url(source_name, record_id):
    """Build a human-readable Europe PMC article URL from source + id."""
    return f"https://europepmc.org/article/{source_name}/{record_id}"


# ---------------------------------------------------------------------------
# default_paper_entry — unified parser for metadata.json
# ---------------------------------------------------------------------------


def default_paper_entry(meta_path):
    """Parse a *metadata.json* file and return ``(identifier, url)``.

    Handles both PubMed esummary-format metadata and Europe PMC search-format
    metadata.  Returns ``("unknown", "URL unavailable; review and refine.")``
    when neither format is recognised.
    """
    try:
        data = json.loads(Path(meta_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "unknown", "URL unavailable; review and refine."

    # PubMed esummary format
    pubmed_result = data.get("result", {})
    if isinstance(pubmed_result, dict) and "uids" in pubmed_result:
        uids = pubmed_result.get("uids", [])
        if len(uids) == 1:
            pmid = str(uids[0])
            return f"PMID:{pmid}", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    # Europe PMC search format
    epmc_results = data.get("resultList", {}).get("result", [])
    if epmc_results:
        record = epmc_results[0]
        source = str(record.get("source") or "EPMC")
        rid = str(record.get("id") or record.get("pmid") or "unknown")
        return f"{source}:{rid}", europe_pmc_article_url(source, rid)

    return "unknown", "URL unavailable; review and refine."


# ---------------------------------------------------------------------------
# resolve_doi_to_id — shared DOI resolution (used by media-db and media-db-lookup)
# ---------------------------------------------------------------------------


def resolve_doi_to_id(doi, email=None, pubmed_fetch_func=None, epmc_fetch_func=None):
    """Resolve a DOI to an identifier via PubMed (preferred) or Europe PMC.

    Returns a ``(source, identifier)`` tuple where *source* is ``"pubmed"``
    or ``"europe-pmc"``, or ``(None, None)`` if the DOI cannot be resolved.

    For PubMed the identifier is a PMID string.
    For Europe PMC the identifier is a ``"SOURCE:ID"`` string.

    *pubmed_fetch_func* and *epmc_fetch_func* allow callers to inject test
    doubles; when ``None`` the real network fetch helpers are used.
    """
    pubmed_fetch = pubmed_fetch_func or fetch_pubmed
    epmc_fetch = epmc_fetch_func or fetch_europe_pmc

    # Try PubMed first
    try:
        params = {"db": "pubmed", "retmode": "json", "term": f"{doi}[doi]", "tool": "media-db"}
        if email:
            params["email"] = email
        raw = pubmed_fetch("esearch.fcgi", params)
        data = json.loads(raw)
        idlist = data.get("esearchresult", {}).get("idlist", [])
        if idlist:
            return ("pubmed", str(idlist[0]))
    except (RuntimeError, json.JSONDecodeError):
        pass

    # Fall back to Europe PMC
    try:
        params = {"query": doi, "resultType": "core", "format": "json", "pageSize": "1"}
        raw = epmc_fetch("search", params)
        data = json.loads(raw)
        hits = data.get("resultList", {}).get("result", [])
        if hits:
            record = hits[0]
            source_name = str(record.get("source") or "MED")
            record_id = str(record.get("id") or record.get("pmid") or "")
            if record_id:
                return ("europe-pmc", f"{source_name}:{record_id}")
    except (RuntimeError, json.JSONDecodeError):
        pass

    return (None, None)


# ---------------------------------------------------------------------------
# _strip_html — lightweight HTML → plain-text
# ---------------------------------------------------------------------------


def _strip_html(text):
    """Strip HTML tags, decode entities, collapse whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = _html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# wrap_text — word-wrap a string to a given width
# ---------------------------------------------------------------------------


def wrap_text(text, width=80):
    """Word-wrap *text* to *width* columns, returning a list of lines."""
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        if not current_line:
            current_line = word
        elif len(current_line) + len(word) + 1 > width:
            lines.append(current_line)
            current_line = word
        else:
            current_line = f"{current_line} {word}"
    if current_line:
        lines.append(current_line)
    return lines


# ---------------------------------------------------------------------------
# YAML frontmatter
# ---------------------------------------------------------------------------


def build_frontmatter(fields):
    """Build a YAML frontmatter block from a dict of fields."""
    lines = ["---"]
    for key, value in fields.items():
        if value is None:
            continue
        val = str(value).strip()
        if not val:
            continue
        # Quote values that contain special YAML characters
        # Quote values containing characters that are YAML-special at the start
        # of an unquoted scalar.  Hyphen (-) is NOT included because it is only
        # special as the first character (sequence entry); leading-hyphen values
        # are extremely rare in frontmatter.
        if any(ch in val for ch in (":", "#", "{", "}", "[", "]", ",", "&", "*", "?", "|", "<", ">", "=", "!", "%", "@", "`")):
            val = val.replace('"', '\\"')
            lines.append(f'{key}: "{val}"')
        else:
            lines.append(f"{key}: {val}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def parse_frontmatter(text):
    """Parse YAML frontmatter from a markdown file. Returns dict or None."""
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    if end == -1:
        return None
    block = text[3:end].strip()
    if not block:
        return None

    data = {}
    lines = block.split("\n")
    current_key = None
    current_value = None

    for line in lines:
        if line.startswith(" ") or line.startswith("\t"):
            if current_key is not None:
                current_value = (current_value or "") + " " + line.strip()
            continue

        if current_key is not None:
            data[current_key] = current_value.strip() if current_value else ""

        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.*)", line)
        if match:
            current_key = match.group(1)
            raw_value = match.group(2).strip()
            if raw_value.startswith('"') and raw_value.endswith('"'):
                current_value = raw_value[1:-1]
            elif raw_value.startswith("'") and raw_value.endswith("'"):
                current_value = raw_value[1:-1]
            else:
                current_value = raw_value
        else:
            current_key = None
            current_value = None

    if current_key is not None:
        data[current_key] = current_value.strip() if current_value else ""

    return data


# =============================================================================
# media-db integrity check — shared library
# =============================================================================
#
# These functions are used by both the standalone media-db-integrity-check CLI
# (thin wrapper in media-db-integrity-check.py) and by every script that modifies
# media-db/ (media-db.py, media-db-setup-dsm5.py, etc.).  After a modification, call
# ``verify_and_report_integrity(root)`` — it returns 0 on success and prints
# actionable error details on failure so an agent can fix issues immediately.

from collections import Counter as _Counter

# --- finding model -----------------------------------------------------------

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

CATEGORY_STRUCTURAL = "structural"
CATEGORY_INDEX = "index"
CATEGORY_METADATA = "metadata"
CATEGORY_SEARCH = "search"
CATEGORY_WEB = "web"
CATEGORY_GUIDELINE = "guideline"


def finding(severity, category, location, description, fix_hint):
    """Create a structured finding dict."""
    return {
        "severity": severity,
        "category": category,
        "location": location,
        "description": description,
        "fix": fix_hint,
    }


# --- tiny helpers ------------------------------------------------------------


def _read_text(path):
    return Path(path).read_text(encoding="utf-8")


def _indexed_paths(data, key):
    """Return sorted list of ``path`` values from an index category."""
    return sorted(entry["path"] for entry in data.get(key, []))


# --- check functions — each appends to ``findings`` --------------------------


def check_required_dirs(root, findings):
    for name in ("searches", "papers", "fulltext", "guidelines", "web"):
        p = root / name
        if not p.is_dir():
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    CATEGORY_STRUCTURAL,
                    str(p),
                    f"Required top-level directory is missing: {name}/",
                    f"Run any archival command (e.g. 'uv run media-db --pmid 12345678') to bootstrap the directory tree.",
                )
            )


def check_empty_files(root, findings):
    for p in root.rglob("*"):
        if p.is_file() and p.stat().st_size == 0:
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    CATEGORY_STRUCTURAL,
                    str(p.relative_to(root)),
                    "File is empty (zero bytes).",
                    "Remove the empty file or populate it with valid content.",
                )
            )


def check_index_valid(root, findings):
    index_path = root / "index.json"
    if not index_path.is_file():
        findings.append(
            finding(
                SEVERITY_ERROR,
                CATEGORY_INDEX,
                "index.json",
                "index.json is missing — the archive has no master index.",
                "Run any archival command to auto-create index.json, or restore from backup.",
            )
        )
        return None

    try:
        data = json.loads(_read_text(index_path))
    except json.JSONDecodeError as exc:
        findings.append(
            finding(
                SEVERITY_ERROR,
                CATEGORY_INDEX,
                "index.json",
                f"index.json is not valid JSON: {exc}",
                "Fix the JSON syntax error or restore from a known-good backup.",
            )
        )
        return None
    except OSError as exc:
        findings.append(
            finding(
                SEVERITY_ERROR,
                CATEGORY_INDEX,
                "index.json",
                f"Cannot read index.json: {exc}",
                "Check file permissions and disk health.",
            )
        )
        return None

    expected_keys = {"searches", "papers", "fulltext", "guidelines", "web"}
    actual_keys = set(data.keys())
    missing_keys = expected_keys - actual_keys
    extra_keys = actual_keys - expected_keys

    for key in sorted(missing_keys):
        findings.append(
            finding(
                SEVERITY_ERROR,
                CATEGORY_INDEX,
                "index.json",
                f"index.json is missing required top-level key: \"{key}\"",
                f"Add a \"{key}\": [] entry to index.json.",
            )
        )
    for key in sorted(extra_keys):
        findings.append(
            finding(
                SEVERITY_WARNING,
                CATEGORY_INDEX,
                "index.json",
                f"index.json contains unrecognised top-level key: \"{key}\"",
                "Remove the key if it is stale; otherwise update the validator to recognise it.",
            )
        )

    if missing_keys:
        return None  # can't proceed with cross-reference checks

    # Duplicate paths within each category
    for key in sorted(expected_keys):
        paths = [entry.get("path", "") for entry in data.get(key, [])]
        dup_counts = {p: c for p, c in _Counter(paths).items() if c > 1}
        for p, count in sorted(dup_counts.items()):
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    CATEGORY_INDEX,
                    f"index.json → {key}",
                    f"Duplicate path appears {count}× in \"{key}\" index: {p}",
                    "Remove the duplicate entries, keeping only one copy.",
                )
            )

    return data


def check_index_crossref(root, data, findings):
    """Cross-reference index.json entries against the filesystem."""
    actual_searches = sorted(
        str(p.relative_to(root))
        for p in (root / "searches").rglob("*.json")
        if (root / "searches").is_dir()
    )
    actual_papers = sorted(
        str(p.parent.relative_to(root))
        for p in (root / "papers").rglob("metadata.json")
        if (root / "papers").is_dir()
    )
    actual_fulltext = sorted(
        str(p.parent.relative_to(root))
        for p in (root / "fulltext").rglob("metadata.json")
        if (root / "fulltext").is_dir()
    )
    actual_guidelines = sorted(
        set(
            str(p.parent.relative_to(root))
            for pattern in ("source.md", "source.*.md")
            for p in (root / "guidelines").rglob(pattern)
            if (root / "guidelines").is_dir()
        )
    )
    actual_web = sorted(
        str(p.relative_to(root))
        for p in (root / "web").rglob("*")
        if p.is_file() and (root / "web").is_dir()
    )

    index_searches = _indexed_paths(data, "searches")
    index_papers = _indexed_paths(data, "papers")
    index_fulltext = _indexed_paths(data, "fulltext")
    index_guidelines = _indexed_paths(data, "guidelines")
    index_web = _indexed_paths(data, "web")

    for label, indexed, on_disk, category in (
        ("search", index_searches, actual_searches, CATEGORY_SEARCH),
        ("paper", index_papers, actual_papers, CATEGORY_METADATA),
        ("fulltext", index_fulltext, actual_fulltext, CATEGORY_METADATA),
        ("guideline", index_guidelines, actual_guidelines, CATEGORY_GUIDELINE),
        ("web", index_web, actual_web, CATEGORY_WEB),
    ):
        missing = sorted(set(indexed) - set(on_disk))
        extra = sorted(set(on_disk) - set(indexed))

        for item in missing:
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    category,
                    item,
                    f"Indexed in index.json → {label}s but not found on disk.",
                    "Remove the stale index entry, or restore the missing file from backup.",
                )
            )
        for item in extra:
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    category,
                    item,
                    f"Exists on disk but is not listed in index.json → {label}s.",
                    f"Add an entry to the \"{label}s\" array in index.json for this file/directory.",
                )
            )


def check_paper_integrity(root, findings):
    papers_dir = root / "papers"
    if not papers_dir.is_dir():
        return

    for meta_file in sorted(papers_dir.rglob("metadata.json")):
        paper_dir = meta_file.parent
        rel_dir = str(paper_dir.relative_to(root))

        # abstract.txt
        abstract_file = paper_dir / "abstract.txt"
        if not abstract_file.is_file():
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    CATEGORY_METADATA,
                    rel_dir,
                    "Paper directory is missing abstract.txt.",
                    f"Fetch the abstract: uv run media-db --pmid <PMID> (or restore from backup).",
                )
            )

        # Validate metadata.json JSON
        try:
            meta = json.loads(_read_text(meta_file))
        except json.JSONDecodeError as exc:
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    CATEGORY_METADATA,
                    f"{rel_dir}/metadata.json",
                    f"metadata.json is not valid JSON: {exc}",
                    "Fix the JSON syntax error or re-fetch with uv run media-db --pmid <PMID>.",
                )
            )
            continue

        # PMID / EPMC folder-name match
        folder_name = paper_dir.name

        pmid_match = re.match(r"pmid-(\d+)-.+", folder_name)
        if pmid_match:
            expected_pmid = pmid_match.group(1)
            uids = meta.get("result", {}).get("uids", [])
            if len(uids) != 1:
                findings.append(
                    finding(
                        SEVERITY_ERROR,
                        CATEGORY_METADATA,
                        f"{rel_dir}/metadata.json",
                        f"Expected 1 PubMed UID, found {len(uids)}.",
                        "Re-fetch metadata with uv run media-db --pmid <PMID>.",
                    )
                )
            elif uids[0] != expected_pmid:
                findings.append(
                    finding(
                        SEVERITY_ERROR,
                        CATEGORY_METADATA,
                        f"{rel_dir}/metadata.json",
                        f"PMID mismatch: folder name expects {expected_pmid}, metadata has {uids[0]}.",
                        "The folder may have been renamed incorrectly. Verify and fix the folder name or re-fetch.",
                    )
                )
            continue

        epmc_match = re.match(r"epmc-([a-z0-9]+)-([a-z0-9]+)-.+", folder_name)
        if epmc_match:
            expected_source = epmc_match.group(1).upper()
            expected_id_slug = epmc_match.group(2)
            results = meta.get("resultList", {}).get("result", [])
            if len(results) != 1:
                findings.append(
                    finding(
                        SEVERITY_ERROR,
                        CATEGORY_METADATA,
                        f"{rel_dir}/metadata.json",
                        f"Expected 1 Europe PMC result, found {len(results)}.",
                        "Re-fetch metadata with uv run media-db --source europe-pmc --epmc-record <ID>.",
                    )
                )
            else:
                record = results[0]
                source_name = str(record.get("source") or "").upper()
                record_id = str(record.get("id") or record.get("pmid") or "")
                if source_name != expected_source:
                    findings.append(
                        finding(
                            SEVERITY_ERROR,
                            CATEGORY_METADATA,
                            f"{rel_dir}/metadata.json",
                            f"Europe PMC source mismatch: folder expects {expected_source}, metadata has {source_name}.",
                            "Verify folder name or re-fetch with correct record ID.",
                        )
                    )
                if slugify(record_id) != expected_id_slug:
                    findings.append(
                        finding(
                            SEVERITY_ERROR,
                            CATEGORY_METADATA,
                            f"{rel_dir}/metadata.json",
                            f"Europe PMC ID mismatch: folder expects slug {expected_id_slug}, metadata slug is {slugify(record_id)}.",
                            "Verify folder name or re-fetch with correct record ID.",
                        )
                    )
            continue

        findings.append(
            finding(
                SEVERITY_WARNING,
                CATEGORY_METADATA,
                rel_dir,
                f"Unrecognised paper folder naming pattern: \"{folder_name}\".",
                "Rename to match pmid-<N>-<title-slug> or epmc-<source>-<id>-<title-slug>.",
            )
        )

    # Check abstract content (non-empty after stripping)
    for abs_file in sorted(papers_dir.rglob("abstract.txt")):
        rel = str(abs_file.relative_to(root))
        try:
            content = _read_text(abs_file).strip()
        except OSError as exc:
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    CATEGORY_METADATA,
                    rel,
                    f"Cannot read abstract.txt: {exc}",
                    "Check file permissions.",
                )
            )
            continue
        if not content:
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    CATEGORY_METADATA,
                    rel,
                    "abstract.txt exists but contains only whitespace.",
                    "Fetch the abstract: uv run media-db --pmid <PMID>.",
                )
            )


def check_search_json(root, findings):
    searches_dir = root / "searches"
    if not searches_dir.is_dir():
        return

    for path in sorted(searches_dir.rglob("*.json")):
        rel = str(path.relative_to(root))
        try:
            data = json.loads(_read_text(path))
        except json.JSONDecodeError as exc:
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    CATEGORY_SEARCH,
                    rel,
                    f"Search JSON is not valid JSON: {exc}",
                    "Re-run the search or restore from backup.",
                )
            )
            continue
        except OSError as exc:
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    CATEGORY_SEARCH,
                    rel,
                    f"Cannot read search file: {exc}",
                    "Check file permissions.",
                )
            )
            continue

        if not isinstance(data, dict):
            continue

        # PubMed esearch format
        pubmed_result = data.get("esearchresult", {})
        if data.get("header", {}).get("type") == "esearch" and pubmed_result:
            if "idlist" not in pubmed_result:
                findings.append(
                    finding(
                        SEVERITY_ERROR,
                        CATEGORY_SEARCH,
                        rel,
                        "PubMed esearch result is missing \"idlist\".",
                        "Re-run the PubMed search.",
                    )
                )
            if "querytranslation" not in pubmed_result:
                findings.append(
                    finding(
                        SEVERITY_WARNING,
                        CATEGORY_SEARCH,
                        rel,
                        "PubMed esearch result is missing \"querytranslation\".",
                        "The search may be truncated or malformed — re-run if results look incomplete.",
                    )
                )
            continue

        # Europe PMC search format
        epmc_request = data.get("request", {})
        epmc_results = data.get("resultList", {})
        if epmc_request and epmc_results is not None:
            if not epmc_request.get("queryString"):
                findings.append(
                    finding(
                        SEVERITY_WARNING,
                        CATEGORY_SEARCH,
                        rel,
                        "Europe PMC search is missing \"queryString\" in request.",
                        "The search file may be incomplete — re-run if needed.",
                    )
                )
            if "result" not in epmc_results:
                findings.append(
                    finding(
                        SEVERITY_WARNING,
                        CATEGORY_SEARCH,
                        rel,
                        "Europe PMC search has no \"result\" in resultList (possibly zero hits).",
                        "Verify the search query was correct; otherwise this is expected for zero-hit queries.",
                    )
                )
            continue
        if epmc_request:
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    CATEGORY_SEARCH,
                    rel,
                    "Europe PMC response is missing resultList.",
                    "The file may be truncated — re-run the search.",
                )
            )
            continue

        # Google Scholar / web search (just a JSON blob)
        if isinstance(data, dict) and data:
            continue

        findings.append(
            finding(
                SEVERITY_WARNING,
                CATEGORY_SEARCH,
                rel,
                "Unrecognised search JSON format (not PubMed esearch or Europe PMC).",
                "Verify the file is a valid search artifact; if so, this warning can be ignored.",
            )
        )


def check_web_files(root, findings):
    web_dir = root / "web"
    if not web_dir.is_dir():
        return

    for path in sorted(web_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root))
        try:
            content = _read_text(path)
        except OSError as exc:
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    CATEGORY_WEB,
                    rel,
                    f"Cannot read web file: {exc}",
                    "Check file permissions.",
                )
            )
            continue

        if not content.strip():
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    CATEGORY_WEB,
                    rel,
                    "Web file is empty (no content after stripping whitespace).",
                    "Remove or re-download the file.",
                )
            )

        if path.suffix == ".html" and "<html" not in content.lower():
            findings.append(
                finding(
                    SEVERITY_WARNING,
                    CATEGORY_WEB,
                    rel,
                    "HTML file does not contain <html> tag — may not be valid HTML.",
                    "Re-download the page if the content looks incomplete.",
                )
            )


def check_guideline_integrity(root, findings):
    guidelines_dir = root / "guidelines"
    if not guidelines_dir.is_dir():
        return

    for src_file in sorted(guidelines_dir.rglob("source.md")):
        rel = str(src_file.relative_to(root))
        try:
            content = _read_text(src_file)
        except OSError as exc:
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    CATEGORY_GUIDELINE,
                    rel,
                    f"Cannot read guideline source file: {exc}",
                    "Check file permissions.",
                )
            )
            continue

        if not content.strip():
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    CATEGORY_GUIDELINE,
                    rel,
                    "Guideline source.md is empty.",
                    "Restore from backup or re-run the setup command (e.g. uv run media-db-setup-dsm5).",
                )
            )

        # Check for YAML frontmatter
        if not content.startswith("---"):
            findings.append(
                finding(
                    SEVERITY_WARNING,
                    CATEGORY_GUIDELINE,
                    rel,
                    "Guideline source.md is missing YAML frontmatter (does not start with ---).",
                    "Add proper frontmatter with title, authors, source, source_url, access_date, language, and extraction_notes.",
                )
            )

    # Also check source.*.md files (e.g. source.de.md)
    for src_file in sorted(guidelines_dir.rglob("source.*.md")):
        rel = str(src_file.relative_to(root))
        try:
            content = _read_text(src_file)
        except OSError as exc:
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    CATEGORY_GUIDELINE,
                    rel,
                    f"Cannot read guideline source file: {exc}",
                    "Check file permissions.",
                )
            )
            continue
        if not content.strip():
            findings.append(
                finding(
                    SEVERITY_ERROR,
                    CATEGORY_GUIDELINE,
                    rel,
                    "Guideline source file is empty.",
                    "Restore from backup or re-run the setup command.",
                )
            )


def check_legacy_dirs(root, findings):
    """Warn about old flat directories left over from pre-migration layouts."""
    for name in ("metadata", "abstracts"):
        legacy = root / name
        if legacy.is_dir():
            findings.append(
                finding(
                    SEVERITY_WARNING,
                    CATEGORY_STRUCTURAL,
                    str(legacy),
                    f"Legacy flat directory \"{name}/\" still exists after migration.",
                    f"Verify all content has been migrated to papers/, then remove: rm -rf {legacy}",
                )
            )


# --- orchestration -----------------------------------------------------------


def run_integrity_check(root):
    """Run all integrity checks on *root* and return a list of finding dicts.

    Does NOT format output or exit — purely a library function.  Callers
    (CLI wrapper, modifying scripts) decide how to present results.
    """
    root = Path(root)
    findings = []

    if not root.is_dir():
        findings.append(
            finding(
                SEVERITY_ERROR,
                CATEGORY_STRUCTURAL,
                str(root),
                f"media-db directory not found: {root}",
                "Create the directory or check the path.",
            )
        )
        return findings

    # Phase 1: structural checks (fast, no index needed)
    check_required_dirs(root, findings)

    fatal_structural = [
        f for f in findings
        if f["severity"] == SEVERITY_ERROR and f["category"] == CATEGORY_STRUCTURAL
    ]
    if fatal_structural:
        check_empty_files(root, findings)
        return findings

    check_empty_files(root, findings)

    # Phase 2: index-dependent checks
    data = check_index_valid(root, findings)
    if data is not None:
        check_index_crossref(root, data, findings)

    # Phase 3: content integrity
    check_paper_integrity(root, findings)
    check_search_json(root, findings)
    check_web_files(root, findings)
    check_guideline_integrity(root, findings)

    # Phase 4: legacy / cleanup
    check_legacy_dirs(root, findings)

    return findings


def verify_and_report_integrity(root):
    """Run integrity check, print issues, return 0 (clean) or 1 (errors).

    Designed for use at the end of every script that modifies media-db/.
    Silent on success; prints a compact error report to stderr on failure
    so the calling agent can see and fix issues immediately.
    """
    findings = run_integrity_check(root)
    errors = [f for f in findings if f["severity"] == SEVERITY_ERROR]
    warnings = [f for f in findings if f["severity"] == SEVERITY_WARNING]

    if not findings:
        return 0

    # Compact error report to stderr
    print("\n--- media-db integrity check ---", file=_sys.stderr)
    for f in errors + warnings:
        prefix = "ERROR" if f["severity"] == SEVERITY_ERROR else "WARNING"
        print(f"{prefix} [{f['category']}] {f['location']}", file=_sys.stderr)
        print(f"  Problem: {f['description']}", file=_sys.stderr)
        print(f"  Fix: {f['fix']}", file=_sys.stderr)

    if errors:
        print(
            f"\n✗ Integrity check FAILED: {len(errors)} error(s), {len(warnings)} warning(s). "
            f"Fix the errors above to prevent data loss.",
            file=_sys.stderr,
        )
        return 1
    else:
        print(
            f"✓ Integrity check passed with {len(warnings)} warning(s).",
            file=_sys.stderr,
        )
        return 0


# ---------------------------------------------------------------------------
# run_cli — canonical CLI entry-point wrapper
# ---------------------------------------------------------------------------


def run_cli(main_func):
    """Run *main_func* as a CLI entry point with KeyboardInterrupt handling.

    Usage::

        if __name__ == "__main__":
            utils.run_cli(main)
    """
    try:
        raise SystemExit(main_func())
    except KeyboardInterrupt:
        print("cancelled", file=_sys.stderr)
        raise SystemExit(130)
