"""Query the local media-db archive.

Provides CLI access to inspect the media-db filesystem structure: list topics,
check whether a PMID or Europe PMC record is already archived, extract PMID
lists from search JSON files, read paper metadata, and search by keyword.

All operations are read-only filesystem queries. No network calls.
"""

import argparse
import json
import sys
from pathlib import Path

import utils


# Re-export canonical slugify for convenience
slugify = utils.slugify


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"error reading {path}: {exc}", file=sys.stderr)
        return None


def _read_json_with_error(path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, f"invalid metadata json: {exc}"
    except OSError as exc:
        return None, f"could not read metadata json: {exc}"


def _paper_metadata(paper_dir):
    meta, error = _read_json_with_error(paper_dir / "metadata.json")
    if meta is None:
        return {"error": error}, None

    pubmed_result = meta.get("result", {})
    uids = pubmed_result.get("uids", []) if isinstance(pubmed_result, dict) else []
    if uids:
        pmid = str(uids[0]) if len(uids) == 1 else None
        record = pubmed_result.get(str(pmid), {}) if pmid else {}
        title = record.get("title", "Unknown title")
        authors = [a.get("name", "") for a in record.get("authors", [])]
        doi = next(
            (aid.get("value", "") for aid in record.get("articleids", []) if aid.get("idtype") == "doi"),
            None,
        )
        journal = record.get("source", "")
        pub_date = record.get("pubdate", "")
        return {
            "source": "pubmed",
            "pmid": pmid,
            "doi": doi,
            "title": title,
            "authors": authors,
            "journal": journal,
            "publication_date": pub_date,
        }, meta

    epmc_results = meta.get("resultList", {}).get("result", [])
    if epmc_results:
        record = epmc_results[0]
        source_name = str(record.get("source") or "EPMC")
        record_id = str(record.get("id") or record.get("pmid") or "")
        return {
            "source": "europe-pmc",
            "epmc_id": f"{source_name}:{record_id}",
            "pmid": record.get("pmid"),
            "doi": record.get("doi"),
            "title": record.get("title", "Unknown title"),
            "authors": [a for a in str(record.get("authorString", "")).split(", ") if a],
            "journal": record.get("journalTitle", ""),
            "publication_date": record.get("firstPublicationDate", ""),
        }, meta

    return {"error": "unrecognized metadata format"}, meta


# ---------------------------------------------------------------------------
# Core query functions
# ---------------------------------------------------------------------------


def list_topics(media_db):
    """List all topics with paper and search counts."""
    topics = {}  # topic → dict

    papers_dir = media_db / "papers"
    searches_dir = media_db / "searches"

    for parent_dir, key in (
        (papers_dir, "paper_count"),
        (searches_dir, "search_count"),
    ):
        if not parent_dir.is_dir():
            continue
        for child in sorted(parent_dir.iterdir()):
            if not child.is_dir():
                continue
            topic = child.name
            entry = topics.setdefault(
                topic, {"topic": topic, "paper_count": 0, "search_count": 0}
            )
            if key == "paper_count":
                entry["paper_count"] = sum(
                    1 for p in child.rglob("metadata.json") if p.is_file()
                )
            else:
                entry["search_count"] = sum(
                    1 for p in child.rglob("*.json") if p.is_file()
                )

    return sorted(topics.values(), key=lambda t: t["topic"])


def list_topic_papers(media_db, topic):
    """List all papers archived under a topic."""
    topic_dir = media_db / "papers" / topic
    if not topic_dir.is_dir():
        return []

    papers = []
    for paper_dir in sorted(topic_dir.iterdir()):
        if not paper_dir.is_dir():
            continue
        meta_file = paper_dir / "metadata.json"
        if not meta_file.is_file():
            continue
        info, _ = _paper_metadata(paper_dir)
        if info and "error" not in info:
            title = info.get("title", "Unknown title")
            if info.get("source") == "pubmed" and info.get("pmid"):
                ident = f"PMID:{info['pmid']}"
                url = f"https://pubmed.ncbi.nlm.nih.gov/{info['pmid']}/"
            elif info.get("source") == "europe-pmc" and info.get("epmc_id"):
                ident = info["epmc_id"]
                source_name, rid = info["epmc_id"].split(":", 1)
                url = utils.europe_pmc_article_url(source_name, rid)
            else:
                ident, url = utils.default_paper_entry(meta_file)
        else:
            ident, url = utils.default_paper_entry(meta_file)
            title = "Unknown title"
        papers.append({
            "folder": str(paper_dir.relative_to(media_db)),
            "identifier": ident,
            "url": url,
            "title": title,
        })
    return papers


def check_pmid_archived(media_db, pmid):
    """Check if a PMID is already archived anywhere under papers/."""
    papers_dir = media_db / "papers"
    if not papers_dir.is_dir():
        return {"pmid": pmid, "archived": False, "locations": []}

    prefix = f"pmid-{pmid}-"
    locations = []
    for paper_dir in sorted(papers_dir.rglob(f"{prefix}*")):
        if paper_dir.is_dir() and (paper_dir / "metadata.json").is_file():
            locations.append(str(paper_dir.relative_to(media_db)))

    return {
        "pmid": pmid,
        "archived": len(locations) > 0,
        "locations": locations,
    }


def check_epmc_archived(media_db, source, record_id):
    """Check if a Europe PMC record is already archived anywhere under papers/."""
    papers_dir = media_db / "papers"
    if not papers_dir.is_dir():
        return {"source": source, "record_id": record_id, "archived": False, "locations": []}

    id_slug = slugify(record_id, fallback="unknown")
    source_lower = source.lower()
    prefix = f"epmc-{source_lower}-{id_slug}-"
    locations = []
    for paper_dir in sorted(papers_dir.rglob(f"{prefix}*")):
        if paper_dir.is_dir() and (paper_dir / "metadata.json").is_file():
            locations.append(str(paper_dir.relative_to(media_db)))

    return {
        "source": source,
        "record_id": record_id,
        "archived": len(locations) > 0,
        "locations": locations,
    }


def extract_pmids_from_search(search_path):
    """Extract PMID list from a PubMed or Europe PMC search JSON file."""
    data = _read_json(search_path)
    if data is None:
        return []

    pubmed_result = data.get("esearchresult", {})
    if pubmed_result and "idlist" in pubmed_result:
        return pubmed_result["idlist"]

    epmc_results = data.get("resultList", {}).get("result", [])
    if epmc_results:
        pmids = []
        for record in epmc_results:
            pmid = record.get("pmid")
            if pmid:
                pmids.append(str(pmid))
        return pmids

    return []


def read_paper_metadata(paper_dir):
    """Read structured metadata from a paper directory."""
    info, _ = _paper_metadata(Path(paper_dir))
    if info is None or "error" in info:
        detail = info.get("error") if info else "unknown error"
        return {"error": f"could not parse metadata from {paper_dir}: {detail}"}
    return info


def search_keyword(media_db, keyword, topic=None):
    """Search papers by keyword in title and abstract. Case-insensitive."""
    papers_dir = media_db / "papers"
    search_root = papers_dir / topic if topic else papers_dir
    if not search_root.is_dir():
        return []

    keyword_lower = keyword.lower()
    matches = []

    for meta_path in sorted(search_root.rglob("metadata.json")):
        paper_dir = meta_path.parent
        info, _ = _paper_metadata(paper_dir)
        if info is None or "error" in info:
            continue

        title = str(info.get("title", "")).lower()
        match_field = []
        match_snippet = ""

        if keyword_lower in title:
            match_field.append("title")
            idx = title.index(keyword_lower)
            start = max(0, idx - 30)
            end = min(len(title), idx + len(keyword_lower) + 30)
            match_snippet = ("..." if start > 0 else "") + str(info.get("title", ""))[start:end] + ("..." if end < len(title) else "")

        abstract_path = paper_dir / "abstract.txt"
        abstract = ""
        abstract_lower = ""
        if abstract_path.is_file():
            try:
                abstract = abstract_path.read_text(encoding="utf-8")
                abstract_lower = abstract.lower()
            except OSError:
                pass
        if keyword_lower in abstract_lower:
            match_field.append("abstract")
            if not match_snippet:
                idx = abstract_lower.index(keyword_lower)
                start = max(0, idx - 40)
                end = min(len(abstract), idx + len(keyword_lower) + 40)
                match_snippet = ("..." if start > 0 else "") + abstract[start:end] + ("..." if end < len(abstract) else "")

        if match_field:
            ident, url = utils.default_paper_entry(meta_path)
            matches.append({
                "folder": str(paper_dir.relative_to(media_db)),
                "identifier": ident,
                "url": url,
                "title": info.get("title", "Unknown title"),
                "match_field": "+".join(match_field),
                "match_snippet": match_snippet,
            })

    return matches


def read_paper_abstract(paper_dir):
    """Read the abstract.txt from a paper directory.

    Args:
        paper_dir: path to paper directory (e.g. papers/adhd/pmid-12345-title).

    Returns:
        str: abstract text, or error message if not found.
    """
    abstract_path = Path(paper_dir) / "abstract.txt"
    if not abstract_path.is_file():
        return "Abstract file not found."
    try:
        return abstract_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        return f"Could not read abstract: {exc}"


def recent_papers(media_db, count=10):
    """List the most recently added papers from index.json.

    Sorts by ``accessed`` date descending and returns the top *count* entries.
    Only returns paper entries (not searches, fulltext, etc.).

    Args:
        media_db: path to media-db root directory.
        count: maximum number of entries to return (default 10).

    Returns:
        list of dicts with keys: path, identifier, url, title, topic, accessed.
    """
    index_path = media_db / "index.json"
    if not index_path.is_file():
        return []

    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    entries = []
    for paper in data.get("papers", []):
        path_str = paper.get("path", "")
        topic = path_str.split("/")[1] if "/" in path_str else "unknown"
        entries.append({
            "path": path_str,
            "identifier": paper.get("identifier", "unknown"),
            "url": paper.get("url", ""),
            "title": _paper_title_from_path(media_db, path_str),
            "topic": topic,
            "accessed": paper.get("accessed", ""),
        })

    entries.sort(key=lambda e: e["accessed"], reverse=True)
    return entries[:count]


def _paper_title_from_path(media_db, rel_path):
    """Read the title from a paper's metadata.json given its index path."""
    meta_path = media_db / rel_path / "metadata.json"
    if not meta_path.is_file():
        return "Unknown title"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "Unknown title"

    pubmed_result = meta.get("result", {})
    if isinstance(pubmed_result, dict) and "uids" in pubmed_result:
        uids = pubmed_result.get("uids", [])
        if uids:
            pmid = str(uids[0])
            record = pubmed_result.get(pmid, {})
            return record.get("title", "Unknown title")

    epmc_results = meta.get("resultList", {}).get("result", [])
    if epmc_results:
        return epmc_results[0].get("title", "Unknown title")

    return "Unknown title"


def search_searches(media_db, keyword, topic=None):
    """Keyword search within archived search JSON files' query text.

    Searches the query/querytranslation field of each search JSON file.
    Case-insensitive.

    Args:
        media_db: path to media-db root directory.
        keyword: keyword to search for.
        topic: optional topic scope (e.g. "adhd").

    Returns:
        list of dicts with keys: path, source, query, match_snippet.
    """
    searches_dir = media_db / "searches"
    search_root = searches_dir / topic if topic else searches_dir
    if not search_root.is_dir():
        return []

    keyword_lower = keyword.lower()
    matches = []

    for search_path in sorted(search_root.rglob("*.json")):
        try:
            data = json.loads(search_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        query_text = ""
        pubmed_result = data.get("esearchresult", {})
        if pubmed_result and "querytranslation" in pubmed_result:
            query_text = pubmed_result.get("querytranslation", "")
        else:
            request = data.get("request", {})
            query_text = request.get("queryString") or request.get("query") or ""

        if keyword_lower in query_text.lower():
            idx = query_text.lower().index(keyword_lower)
            start = max(0, idx - 30)
            end = min(len(query_text), idx + len(keyword_lower) + 30)
            snippet = ("..." if start > 0 else "") + query_text[start:end] + ("..." if end < len(query_text) else "")

            source = "PubMed" if pubmed_result and "querytranslation" in pubmed_result else "Europe PMC"
            matches.append({
                "path": str(search_path.relative_to(media_db)),
                "source": source,
                "query": query_text,
                "match_snippet": snippet,
            })

    return matches


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _format_json(result):
    return json.dumps(result, indent=2, default=str, ensure_ascii=False)


def _format_text(result, command):
    if command == "list-topics":
        if not result.get("topics"):
            return "No topics found."
        lines = ["Topics:"]
        for t in result["topics"]:
            lines.append(f"  {t['topic']}: {t['paper_count']} papers, {t['search_count']} searches")
        return "\n".join(lines)

    if command == "topic-papers":
        papers = result.get("papers", [])
        if not papers:
            return "No papers found for this topic."
        lines = [f"Papers in '{result['topic']}':"]
        for p in papers:
            lines.append(f"  {p['folder']}")
            lines.append(f"    {p['identifier']}")
            lines.append(f"    {p['title'][:120]}")
        return "\n".join(lines)

    if command == "check-pmid":
        if result["archived"]:
            lines = [f"PMID {result['pmid']}: ARCHIVED"]
            for loc in result["locations"]:
                lines.append(f"  {loc}")
        else:
            lines = [f"PMID {result['pmid']}: NOT ARCHIVED"]
        return "\n".join(lines)

    if command == "check-epmc":
        if result["archived"]:
            lines = [f"{result['source']}:{result['record_id']}: ARCHIVED"]
            for loc in result["locations"]:
                lines.append(f"  {loc}")
        else:
            lines = [f"{result['source']}:{result['record_id']}: NOT ARCHIVED"]
        return "\n".join(lines)

    if command == "pmids-from-search":
        pmids = result.get("pmids", [])
        if not pmids:
            return "No PMIDs found in search file."
        lines = [f"PMIDs from {result.get('search_path', 'unknown')} ({len(pmids)} total):"]
        for pmid in pmids:
            lines.append(f"  {pmid}")
        return "\n".join(lines)

    if command == "read-metadata":
        if "error" in result:
            return f"Error: {result['error']}"
        lines = [
            f"Title:  {result.get('title', 'N/A')}",
            f"Source: {result.get('source', 'N/A')}",
            f"PMID:   {result.get('pmid', 'N/A')}",
            f"DOI:    {result.get('doi', 'N/A')}",
            f"Journal:{result.get('journal', 'N/A')} ({result.get('publication_date', 'N/A')})",
        ]
        authors = result.get("authors", [])
        if authors:
            lines.append(f"Authors:{', '.join(authors[:10])}{'...' if len(authors) > 10 else ''}")
        abstract = result.get("abstract")
        if abstract:
            lines.append("")
            lines.append("Abstract:")
            lines.extend(utils.wrap_text(abstract))
        return "\n".join(lines)

    if command == "search-keyword":
        matches = result.get("matches", [])
        if not matches:
            return f"No matches for '{result.get('keyword', '')}'."
        summary = result.get("summary", False)
        if summary:
            lines = [f"Keyword '{result.get('keyword', '')}': {result.get('match_count', len(matches))} match(es)"]
            for m in matches:
                lines.append(f"  {m['identifier']}: {m['title'][:120]}")
            return "\n".join(lines)
        lines = [f"Keyword '{result.get('keyword', '')}': {len(matches)} match(es)"]
        for m in matches:
            lines.append(f"  {m['folder']}")
            lines.append(f"    {m['identifier']}: {m['title'][:100]}")
            lines.append(f"    matched in: {m['match_field']}")
        return "\n".join(lines)

    if command == "recent":
        papers = result.get("papers", [])
        if not papers:
            return "No recently added papers found."
        lines = [f"Recent papers ({len(papers)}):"]
        for p in papers:
            lines.append(f"  {p['accessed']}  {p['identifier']}  [{p['topic']}]")
            lines.append(f"    {p['title'][:120]}")
        return "\n".join(lines)

    if command == "search-searches":
        matches = result.get("matches", [])
        if not matches:
            return f"No matching searches for '{result.get('keyword', '')}'."
        lines = [f"Search keyword '{result.get('keyword', '')}': {len(matches)} match(es)"]
        for m in matches:
            lines.append(f"  {m['path']}")
            lines.append(f"    source: {m['source']}")
            lines.append(f"    query:  {m['query'][:120]}")
        return "\n".join(lines)

    return json.dumps(result, indent=2, default=str, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args():
    parser = argparse.ArgumentParser(
        description="Query the local media-db archive.",
    )
    parser.add_argument(
        "--media-db",
        default="media-db",
        help="Path to media-db root directory. Defaults to ./media-db.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format. Defaults to json.",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list-topics", action="store_true", help="List all topics with paper and search counts.")
    group.add_argument("--topic", type=str, help="List all papers under a topic.")
    group.add_argument("--check-pmid", type=str, help="Check if a PMID is already archived.")
    group.add_argument("--check-epmc", type=str, help="Check if a Europe PMC record (SOURCE:ID) is archived.")
    group.add_argument("--pmids-from-search", type=str, help="Extract PMID list from a search JSON file.")
    group.add_argument("--read-metadata", type=str, help="Read metadata from a paper directory.")
    group.add_argument("--search-keyword", type=str, help="Search papers by keyword (case-insensitive).")
    group.add_argument("--recent", type=int, help="List N most recently added papers.")
    group.add_argument("--search-searches", type=str, help="Search archived search queries by keyword (case-insensitive).")
    parser.add_argument(
        "--search-topic",
        type=str,
        help="Optional topic scope for --search-keyword or --search-searches.",
    )
    parser.add_argument(
        "--show-abstract",
        action="store_true",
        help="Include abstract text with --read-metadata output.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Compact output for --search-keyword (identifiers and titles only, no snippets).",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    media_db = Path(args.media_db)

    if not media_db.is_dir():
        print(json.dumps({"error": f"media-db directory not found: {media_db}"}), file=sys.stderr)
        return 1

    command = None
    result = None

    if args.list_topics:
        command = "list-topics"
        result = {"topics": list_topics(media_db)}
    elif args.topic:
        command = "topic-papers"
        result = {"topic": args.topic, "papers": list_topic_papers(media_db, args.topic)}
    elif args.check_pmid:
        command = "check-pmid"
        result = check_pmid_archived(media_db, args.check_pmid)
    elif args.check_epmc:
        command = "check-epmc"
        try:
            source, record_id = args.check_epmc.split(":", 1)
        except ValueError:
            print(json.dumps({"error": "invalid --check-epmc format; expected SOURCE:ID"}), file=sys.stderr)
            return 1
        result = check_epmc_archived(media_db, source, record_id)
    elif args.pmids_from_search:
        command = "pmids-from-search"
        search_path = Path(args.pmids_from_search)
        if not search_path.is_file():
            print(json.dumps({"error": f"search file not found: {search_path}"}), file=sys.stderr)
            return 1
        pmids = extract_pmids_from_search(search_path)
        result = {"search_path": str(search_path), "pmid_count": len(pmids), "pmids": pmids}
    elif args.read_metadata:
        command = "read-metadata"
        result = read_paper_metadata(args.read_metadata)
        if args.show_abstract and "error" not in result:
            result["abstract"] = read_paper_abstract(args.read_metadata)
    elif args.search_keyword:
        command = "search-keyword"
        matches = search_keyword(media_db, args.search_keyword, topic=args.search_topic)
        result = {
            "keyword": args.search_keyword,
            "match_count": len(matches),
            "matches": matches,
            "summary": args.summary,
        }
    elif args.recent:
        command = "recent"
        papers = recent_papers(media_db, count=args.recent)
        result = {"papers": papers}
    elif args.search_searches:
        command = "search-searches"
        matches = search_searches(media_db, args.search_searches, topic=args.search_topic)
        result = {
            "keyword": args.search_searches,
            "match_count": len(matches),
            "matches": matches,
        }

    if args.format == "text":
        print(_format_text(result, command))
    else:
        print(_format_json(result))

    return 0


if __name__ == "__main__":
    utils.run_cli(main)
