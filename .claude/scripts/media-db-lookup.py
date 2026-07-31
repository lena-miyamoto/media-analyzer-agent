"""Lightweight external lookup — PubMed, Europe PMC, DOI resolution.

Fetches structured paper data (title, abstract, authors, DOI) by PMID,
Europe PMC SOURCE:ID, or DOI. Does NOT archive to media-db — use `media-db`
for archival. Returns JSON to stdout by default; use `--format text` for
human-readable output.

Core lookup functions accept an injectable `fetch_func` parameter so they
can be tested without network calls.
"""

import argparse
import json
import re
import sys
import time
import utils


# Re-export for tests that reference them via the module
slugify = utils.slugify
_strip_html = utils._strip_html
fetch_pubmed = utils.fetch_pubmed
fetch_europe_pmc = utils.fetch_europe_pmc


# ---------------------------------------------------------------------------
# Core lookup functions
# ---------------------------------------------------------------------------


def lookup_pmids(pmids, email=None, fetch_func=None, delay=0):
    """Fetch structured data for one or more PMIDs from PubMed.

    Args:
        pmids: list of PMID strings.
        email: optional NCBI contact email.
        fetch_func: callable(endpoint, params) -> str for testing.
        delay: seconds to sleep between per-PMID efetch calls (rate limiting).

    Returns:
        list of dicts with keys: source, pmid, doi, title, abstract,
        authors, journal, publication_date, url.
    """
    if fetch_func is None:
        fetch_func = fetch_pubmed

    pmids = [str(p) for p in pmids]
    if not pmids:
        return []

    # Batch esummary
    params = {"db": "pubmed", "retmode": "json", "id": ",".join(pmids)}
    if email:
        params["email"] = email
    params["tool"] = "media-db-lookup"

    raw_summary = fetch_func("esummary.fcgi", params)
    summary = json.loads(raw_summary)
    records = summary.get("result", {})

    results = []
    for i, pmid in enumerate(pmids):
        record = records.get(pmid)
        if record is None or "error" in record:
            results.append({"source": "pubmed", "pmid": pmid, "error": "not found"})
            continue

        authors = [a.get("name", "") for a in record.get("authors", [])]
        doi = None
        for aid in record.get("articleids", []):
            if aid.get("idtype") == "doi":
                doi = aid.get("value")
                break

        # Individual efetch for abstract (includes email for NCBI rate limiting)
        try:
            efetch_params = {
                "db": "pubmed",
                "id": pmid,
                "rettype": "abstract",
                "retmode": "text",
                "tool": "media-db-lookup",
            }
            if email:
                efetch_params["email"] = email
            raw_abstract = fetch_func("efetch.fcgi", efetch_params)
            abstract = _extract_abstract_medline(raw_abstract)
        except RuntimeError:
            abstract = "Abstract unavailable."

        results.append({
            "source": "pubmed",
            "pmid": pmid,
            "doi": doi,
            "title": record.get("title", "Unknown title"),
            "abstract": abstract,
            "authors": authors,
            "journal": record.get("source", ""),
            "publication_date": record.get("pubdate", ""),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })

        if delay > 0 and i < len(pmids) - 1:
            time.sleep(delay)

    return results


def _extract_abstract_medline(raw):
    """Extract abstract text from MEDLINE format efetch output.

    Returns the abstract text as a single string, or ``"Abstract
    unavailable."`` if no abstract could be extracted.
    """
    lines = raw.splitlines()
    abstract_lines = []
    in_abstract = False
    for line in lines:
        if line.startswith("AB  - "):
            in_abstract = True
            abstract_lines.append(line[6:])
        elif in_abstract and line.startswith("      "):
            abstract_lines.append(line[6:])
        elif in_abstract and not line.startswith("      "):
            break
    abstract = " ".join(abstract_lines).strip()
    if not abstract:
        match = re.search(r"\bAbstract\s*(?:\n\s*-+\s*)?\n+(.+)", raw, re.DOTALL | re.IGNORECASE)
        if match:
            abstract = match.group(1).strip()
            cutoff = re.search(r"\n\s*(?:Publication types|MeSH terms|Substances|Grant support)\s*\n", abstract, re.IGNORECASE)
            if cutoff:
                abstract = abstract[:cutoff.start()].strip()
            cutoff = re.search(r"\n\s*Copyright\b", abstract, re.IGNORECASE)
            if cutoff:
                abstract = abstract[:cutoff.start()].strip()
    return abstract or "Abstract unavailable."


def lookup_epmc_records(record_specs, fetch_func=None, delay=0):
    """Fetch structured data for one or more Europe PMC SOURCE:ID records.

    Args:
        record_specs: list of "SOURCE:ID" strings (e.g. ["MED:35350465"]).
        fetch_func: callable(module, params) -> str for testing.
        delay: seconds to sleep between per-record fetches (rate limiting).

    Returns:
        list of dicts with keys: source, epmc_id, pmid, doi, title, abstract,
        authors, journal, publication_date, url.
    """
    if fetch_func is None:
        fetch_func = fetch_europe_pmc

    results = []
    for i, spec in enumerate(record_specs):
        try:
            source_name, record_id = spec.split(":", 1)
        except ValueError:
            results.append({"source": "europe-pmc", "epmc_id": spec, "error": "invalid format; expected SOURCE:ID"})
            continue

        source_name = source_name.upper()
        params = {
            "query": f"EXT_ID:{record_id} AND SRC:{source_name}",
            "resultType": "core",
            "format": "json",
            "pageSize": "1",
        }
        try:
            raw = fetch_func("search", params)
            data = json.loads(raw)
            hits = data.get("resultList", {}).get("result", [])
            if not hits:
                results.append({
                    "source": "europe-pmc",
                    "epmc_id": f"{source_name}:{record_id}",
                    "error": "not found",
                })
                continue

            record = hits[0]
            abstract_html = record.get("abstractText") or ""
            abstract = _strip_html(abstract_html) if abstract_html else "Abstract unavailable."

            results.append({
                "source": "europe-pmc",
                "epmc_id": f"{source_name}:{record_id}",
                "pmid": record.get("pmid"),
                "doi": record.get("doi"),
                "title": record.get("title", "Unknown title"),
                "abstract": abstract,
                "authors": [a for a in str(record.get("authorString", "")).split(", ") if a],
                "journal": record.get("journalTitle", ""),
                "publication_date": record.get("firstPublicationDate", ""),
                "url": utils.europe_pmc_article_url(source_name, record_id),
            })
        except RuntimeError as exc:
            results.append({
                "source": "europe-pmc",
                "epmc_id": f"{source_name}:{record_id}",
                "error": str(exc),
            })

        if delay > 0 and i < len(record_specs) - 1:
            time.sleep(delay)

    return results


def resolve_doi(doi, email=None, pubmed_fetch_func=None, epmc_fetch_func=None):
    """Resolve a DOI to its PubMed record.

    Tries PubMed E-utilities first, then falls back to Europe PMC.

    Args:
        doi: DOI string (e.g. "10.1000/xyz").
        email: optional NCBI contact email.
        pubmed_fetch_func: callable(endpoint, params) -> str for PubMed.
        epmc_fetch_func: callable(module, params) -> str for Europe PMC.
            When None, uses the real fetch_pubmed / fetch_europe_pmc.

    Returns:
        dict with keys: source, pmid, doi, title, abstract, authors,
        journal, publication_date, url, or None if not found.
    """
    if pubmed_fetch_func is None:
        pubmed_fetch_func = fetch_pubmed
    if epmc_fetch_func is None:
        epmc_fetch_func = fetch_europe_pmc

    source, identifier = utils.resolve_doi_to_id(
        doi, email=email,
        pubmed_fetch_func=pubmed_fetch_func,
        epmc_fetch_func=epmc_fetch_func,
    )
    if source == "pubmed":
        results = lookup_pmids([identifier], email=email, fetch_func=pubmed_fetch_func)
        return results[0] if results and "error" not in results[0] else None
    elif source == "europe-pmc":
        results = lookup_epmc_records([identifier], fetch_func=epmc_fetch_func)
        return results[0] if results and "error" not in results[0] else None
    return None


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _format_json(results):
    return json.dumps({"results": results}, indent=2, default=str, ensure_ascii=False)


def _format_text(results):
    lines = []
    for index, result in enumerate(results, 1):
        if "error" in result:
            lines.append(f"--- Result {index} ({result.get('source', 'unknown')}) ---")
            lines.append(f"ID:    {result.get('pmid') or result.get('epmc_id') or result.get('doi', 'N/A')}")
            lines.append(f"ERROR: {result['error']}")
            lines.append("")
            continue

        lines.append(f"--- Result {index} ({result['source']}) ---")
        lines.append(f"PMID:    {result.get('pmid', 'N/A')}")
        if result.get("epmc_id"):
            lines.append(f"EPMC ID: {result['epmc_id']}")
        lines.append(f"DOI:     {result.get('doi', 'N/A')}")
        lines.append(f"Title:   {result.get('title', 'N/A')}")
        authors = result.get("authors", [])
        if authors:
            lines.append(f"Authors: {', '.join(authors[:8])}{'...' if len(authors) > 8 else ''}")
        lines.append(f"Journal: {result.get('journal', 'N/A')} ({result.get('publication_date', 'N/A')})")
        lines.append(f"URL:     {result.get('url', 'N/A')}")
        lines.append("")
        abstract = result.get("abstract", "")
        if abstract:
            lines.append(f"Abstract:")
            lines.extend(utils.wrap_text(abstract))
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args():
    parser = argparse.ArgumentParser(
        description="Lightweight external lookup — PubMed, Europe PMC, or DOI resolution. No archival.",
    )
    parser.add_argument(
        "--pmid",
        action="append",
        default=[],
        help="PubMed ID to look up. May be passed multiple times.",
    )
    parser.add_argument(
        "--epmc-record",
        action="append",
        default=[],
        help="Europe PMC record as SOURCE:ID. May be passed multiple times.",
    )
    parser.add_argument(
        "--doi",
        action="append",
        default=[],
        help="DOI to resolve. May be passed multiple times.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format. Defaults to json.",
    )
    parser.add_argument(
        "--email",
        help="Optional contact email passed to NCBI E-utilities.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.34,
        help="Delay between individual fetches in seconds. Defaults to 0.34.",
    )

    args = parser.parse_args()
    if not args.pmid and not args.epmc_record and not args.doi:
        parser.error("provide at least one of --pmid, --epmc-record, or --doi")
    return args


def main():
    args = parse_args()
    results = []

    if args.pmid:
        results.extend(lookup_pmids(args.pmid, email=args.email, delay=args.delay))

    if args.epmc_record:
        results.extend(lookup_epmc_records(args.epmc_record, delay=args.delay))

    for i, doi in enumerate(args.doi):
        record = resolve_doi(doi, email=args.email)
        if record:
            results.append(record)
        else:
            results.append({"source": "unknown", "doi": doi, "error": "DOI not found in PubMed or Europe PMC"})
        if i < len(args.doi) - 1 and args.delay > 0:
            time.sleep(args.delay)

    if args.format == "text":
        print(_format_text(results))
    else:
        print(_format_json(results))

    # Return non-zero if any lookup failed
    return 1 if any("error" in r for r in results) else 0


if __name__ == "__main__":
    utils.run_cli(main)
