"""Tests for media-db-query.py — local archive query operations."""

import json
import sys

import pytest
from pathlib import Path

import media_db_query as mq


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_search_json(path, source, pmids=None, query="test query"):
    """Create a realistic search JSON file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if source == "pubmed":
        data = {
            "header": {"type": "esearch"},
            "esearchresult": {
                "idlist": pmids or [],
                "querytranslation": query,
                "count": str(len(pmids or [])),
            },
        }
    else:
        data = {
            "request": {"queryString": query},
            "resultList": {
                "result": [
                    {"source": "MED", "id": str(pmid), "pmid": str(pmid)}
                    for pmid in (pmids or [])
                ]
            },
        }
    Path(path).write_text(json.dumps(data), encoding="utf-8")


def _make_paper(tmp_path, rel_dir, pmid="12345678", source="pubmed", title="Test Title", abstract="Test abstract content."):
    """Create a paper directory with metadata.json and abstract.txt."""
    paper_dir = tmp_path / rel_dir
    paper_dir.mkdir(parents=True)

    if source == "pubmed":
        meta = {
            "result": {
                "uids": [pmid],
                pmid: {
                    "title": title,
                    "source": "Test Journal",
                    "pubdate": "2024 Mar",
                    "authors": [{"name": "Smith J"}, {"name": "Jones K"}],
                    "articleids": [
                        {"idtype": "pubmed", "value": pmid},
                        {"idtype": "doi", "value": "10.1000/test"},
                    ],
                },
            }
        }
    else:
        meta = {
            "resultList": {
                "result": [{
                    "source": "MED",
                    "id": pmid,
                    "pmid": pmid,
                    "title": title,
                    "authorString": "Smith J, Jones K",
                    "journalTitle": "Test Journal",
                    "firstPublicationDate": "2024-03-01",
                    "doi": "10.1000/test",
                }],
            }
        }

    (paper_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    (paper_dir / "abstract.txt").write_text(abstract, encoding="utf-8")
    return paper_dir


# ---------------------------------------------------------------------------
# list_topics
# ---------------------------------------------------------------------------

class TestListTopics:
    def test_empty_archive(self, tmp_path):
        (tmp_path / "papers").mkdir()
        (tmp_path / "searches").mkdir()
        topics = mq.list_topics(tmp_path)
        assert topics == []

    def test_lists_topics_with_counts(self, tmp_path):
        (tmp_path / "papers" / "adhd").mkdir(parents=True)
        (tmp_path / "papers" / "endo").mkdir(parents=True)
        (tmp_path / "searches" / "adhd").mkdir(parents=True)
        _make_paper(tmp_path, "papers/adhd/pmid-11111-test-a")
        _make_paper(tmp_path, "papers/adhd/pmid-22222-test-b")
        _make_paper(tmp_path, "papers/endo/pmid-33333-test-c")
        _make_search_json(tmp_path / "searches" / "adhd" / "s1.json", "pubmed", ["11111"])

        topics = {t["topic"]: t for t in mq.list_topics(tmp_path)}

        assert len(topics) == 2
        assert topics["adhd"]["paper_count"] == 2
        assert topics["adhd"]["search_count"] == 1
        assert topics["endo"]["paper_count"] == 1
        assert topics["endo"]["search_count"] == 0

    def test_no_searches_dir(self, tmp_path):
        (tmp_path / "papers" / "adhd").mkdir(parents=True)
        _make_paper(tmp_path, "papers/adhd/pmid-11111-test")
        topics = mq.list_topics(tmp_path)
        assert len(topics) == 1
        assert topics[0]["search_count"] == 0


# ---------------------------------------------------------------------------
# list_topic_papers
# ---------------------------------------------------------------------------

class TestListTopicPapers:
    def test_lists_papers(self, tmp_path):
        _make_paper(tmp_path, "papers/adhd/pmid-11111-test-a", pmid="11111", title="Paper A")
        _make_paper(tmp_path, "papers/adhd/pmid-22222-test-b", pmid="22222", title="Paper B")

        papers = mq.list_topic_papers(tmp_path, "adhd")
        assert len(papers) == 2
        assert papers[0]["identifier"] == "PMID:11111"
        assert papers[1]["identifier"] == "PMID:22222"

    def test_empty_topic(self, tmp_path):
        (tmp_path / "papers" / "adhd").mkdir(parents=True)
        papers = mq.list_topic_papers(tmp_path, "adhd")
        assert papers == []

    def test_nonexistent_topic(self, tmp_path):
        papers = mq.list_topic_papers(tmp_path, "adhd")
        assert papers == []

    def test_skips_non_paper_dirs(self, tmp_path):
        (tmp_path / "papers" / "adhd" / "not-a-paper").mkdir(parents=True)
        _make_paper(tmp_path, "papers/adhd/pmid-11111-test")
        papers = mq.list_topic_papers(tmp_path, "adhd")
        assert len(papers) == 1


# ---------------------------------------------------------------------------
# check_pmid_archived
# ---------------------------------------------------------------------------

class TestCheckPmidArchived:
    def test_found(self, tmp_path):
        _make_paper(tmp_path, "papers/adhd/pmid-12345678-effect-of-x")
        result = mq.check_pmid_archived(tmp_path, "12345678")
        assert result["archived"] is True
        assert len(result["locations"]) == 1
        assert "12345678" in result["locations"][0]

    def test_not_found(self, tmp_path):
        (tmp_path / "papers").mkdir()
        result = mq.check_pmid_archived(tmp_path, "12345678")
        assert result["archived"] is False
        assert result["locations"] == []

    def test_no_papers_dir(self, tmp_path):
        result = mq.check_pmid_archived(tmp_path, "12345678")
        assert result["archived"] is False

    def test_matches_exact_pmid(self, tmp_path):
        # Should NOT match pmid-123456789-... when looking for 12345678
        _make_paper(tmp_path, "papers/adhd/pmid-12345678-effect")
        _make_paper(tmp_path, "papers/adhd/pmid-123456789-other")
        result = mq.check_pmid_archived(tmp_path, "12345678")
        assert result["archived"] is True
        assert len(result["locations"]) == 1  # only the exact match


# ---------------------------------------------------------------------------
# check_epmc_archived
# ---------------------------------------------------------------------------

class TestCheckEpmcArchived:
    def test_found(self, tmp_path):
        _make_paper(tmp_path, "papers/adhd/epmc-med-35350465-effect", pmid="35350465", source="europe-pmc")
        result = mq.check_epmc_archived(tmp_path, "MED", "35350465")
        assert result["archived"] is True
        assert len(result["locations"]) == 1

    def test_not_found(self, tmp_path):
        (tmp_path / "papers").mkdir()
        result = mq.check_epmc_archived(tmp_path, "MED", "35350465")
        assert result["archived"] is False

    def test_case_insensitive_source(self, tmp_path):
        _make_paper(tmp_path, "papers/adhd/epmc-med-35350465-effect", pmid="35350465", source="europe-pmc")
        result = mq.check_epmc_archived(tmp_path, "med", "35350465")
        assert result["archived"] is True


# ---------------------------------------------------------------------------
# extract_pmids_from_search
# ---------------------------------------------------------------------------

class TestExtractPmidsFromSearch:
    def test_pubmed_esearch(self, tmp_path):
        _make_search_json(tmp_path / "search.json", "pubmed", ["11111", "22222"])
        pmids = mq.extract_pmids_from_search(tmp_path / "search.json")
        assert pmids == ["11111", "22222"]

    def test_europe_pmc_search(self, tmp_path):
        _make_search_json(tmp_path / "search.json", "europe-pmc", ["33333", "44444"])
        pmids = mq.extract_pmids_from_search(tmp_path / "search.json")
        assert set(pmids) == {"33333", "44444"}

    def test_empty_search(self, tmp_path):
        _make_search_json(tmp_path / "search.json", "pubmed", [])
        pmids = mq.extract_pmids_from_search(tmp_path / "search.json")
        assert pmids == []

    def test_missing_file(self):
        result = mq.extract_pmids_from_search(Path("nonexistent.json"))
        assert result == []


# ---------------------------------------------------------------------------
# read_paper_metadata
# ---------------------------------------------------------------------------

class TestReadPaperMetadata:
    def test_pubmed_metadata(self, tmp_path):
        d = _make_paper(tmp_path, "papers/adhd/pmid-12345678-effect", title="Effect of X on Y")
        info = mq.read_paper_metadata(str(d))
        assert info["source"] == "pubmed"
        assert info["pmid"] == "12345678"
        assert info["doi"] == "10.1000/test"
        assert info["title"] == "Effect of X on Y"
        assert info["authors"] == ["Smith J", "Jones K"]
        assert info["journal"] == "Test Journal"
        assert info["publication_date"] == "2024 Mar"

    def test_epmc_metadata(self, tmp_path):
        d = _make_paper(tmp_path, "papers/adhd/epmc-med-35350465-effect", pmid="35350465", source="europe-pmc")
        info = mq.read_paper_metadata(str(d))
        assert info["source"] == "europe-pmc"
        assert info["pmid"] == "35350465"
        assert info["doi"] == "10.1000/test"

    def test_missing_directory(self):
        result = mq.read_paper_metadata("nonexistent/dir")
        assert "error" in result

    def test_corrupt_metadata(self, tmp_path):
        d = tmp_path / "papers" / "adhd" / "pmid-12345-test"
        d.mkdir(parents=True)
        (d / "metadata.json").write_text("not json")
        result = mq.read_paper_metadata(str(d))
        assert "error" in result
        assert "invalid metadata json" in result["error"]

    def test_unrecognized_metadata(self, tmp_path):
        d = tmp_path / "papers" / "adhd" / "pmid-12345-test"
        d.mkdir(parents=True)
        (d / "metadata.json").write_text(json.dumps({"unexpected": "shape"}))
        result = mq.read_paper_metadata(str(d))
        assert "unrecognized metadata format" in result["error"]


# ---------------------------------------------------------------------------
# search_keyword
# ---------------------------------------------------------------------------

class TestSearchKeyword:
    def test_match_in_title(self, tmp_path):
        _make_paper(tmp_path, "papers/adhd/pmid-11111-effect", title="Effect of Lisdexamfetamine on Attention")
        matches = mq.search_keyword(tmp_path, "lisdexamfetamine")
        assert len(matches) == 1
        assert matches[0]["match_field"] == "title"
        assert "Lisdexamfetamine" in matches[0]["match_snippet"]

    def test_match_in_abstract(self, tmp_path):
        _make_paper(tmp_path, "papers/adhd/pmid-11111-effect", title="Some Paper", abstract="We studied lisdexamfetamine in patients with ADHD.")
        matches = mq.search_keyword(tmp_path, "lisdexamfetamine")
        assert len(matches) == 1
        assert matches[0]["match_field"] == "abstract"
        assert "ADHD" in matches[0]["match_snippet"]

    def test_match_in_both(self, tmp_path):
        _make_paper(tmp_path, "papers/adhd/pmid-11111-effect", title="Lisdexamfetamine Study", abstract="lisdexamfetamine improved outcomes.")
        matches = mq.search_keyword(tmp_path, "lisdexamfetamine")
        assert len(matches) == 1
        assert matches[0]["match_field"] == "title+abstract"

    def test_no_match(self, tmp_path):
        _make_paper(tmp_path, "papers/adhd/pmid-11111-effect", title="Effect of Methylphenidate on Attention", abstract="methylphenidate results.")
        matches = mq.search_keyword(tmp_path, "lisdexamfetamine")
        assert len(matches) == 0

    def test_case_insensitive(self, tmp_path):
        _make_paper(tmp_path, "papers/adhd/pmid-11111-effect", title="Effect of LISDEXAMFETAMINE on Attention")
        matches = mq.search_keyword(tmp_path, "lisdexamfetamine")
        assert len(matches) == 1

    def test_scoped_to_topic(self, tmp_path):
        _make_paper(tmp_path, "papers/adhd/pmid-11111-effect", title="Lisdexamfetamine Study")
        _make_paper(tmp_path, "papers/endo/pmid-22222-other", title="Lisdexamfetamine Other")
        matches = mq.search_keyword(tmp_path, "lisdexamfetamine", topic="adhd")
        assert len(matches) == 1
        assert "adhd" in matches[0]["folder"]

    def test_handles_missing_abstract(self, tmp_path):
        d = tmp_path / "papers" / "adhd" / "pmid-11111-test"
        d.mkdir(parents=True)
        (d / "metadata.json").write_text(json.dumps({
            "result": {
                "uids": ["11111"],
                "11111": {
                    "title": "Lisdexamfetamine Effect",
                    "source": "J Test", "pubdate": "2024", "authors": [],
                    "articleids": [{"idtype": "pubmed", "value": "11111"}],
                },
            }
        }), encoding="utf-8")
        matches = mq.search_keyword(tmp_path, "lisdexamfetamine")
        assert len(matches) == 1
        assert matches[0]["match_field"] == "title"

    def test_skips_unparseable_metadata(self, tmp_path):
        d = tmp_path / "papers" / "adhd" / "pmid-11111-test"
        d.mkdir(parents=True)
        (d / "metadata.json").write_text("not json")
        matches = mq.search_keyword(tmp_path, "lisdexamfetamine")
        assert len(matches) == 0


# ---------------------------------------------------------------------------
# CLI / main
# ---------------------------------------------------------------------------

class TestMain:
    def test_list_topics_json(self, tmp_path, capsys):
        (tmp_path / "papers" / "adhd").mkdir(parents=True)
        _make_paper(tmp_path, "papers/adhd/pmid-11111-test")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", ["media-db-query", "--media-db", str(tmp_path), "--list-topics"])
            try:
                mq.main()
            except SystemExit:
                pass

        out = json.loads(capsys.readouterr().out)
        assert len(out["topics"]) == 1
        assert out["topics"][0]["topic"] == "adhd"

    def test_check_pmid_found(self, tmp_path, capsys):
        _make_paper(tmp_path, "papers/adhd/pmid-99999999-effect")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", ["media-db-query", "--media-db", str(tmp_path), "--check-pmid", "99999999"])
            try:
                mq.main()
            except SystemExit:
                pass

        out = json.loads(capsys.readouterr().out)
        assert out["archived"] is True
        assert len(out["locations"]) == 1

    def test_check_pmid_not_found(self, tmp_path, capsys):
        (tmp_path / "papers").mkdir()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", ["media-db-query", "--media-db", str(tmp_path), "--check-pmid", "99999999"])
            try:
                mq.main()
            except SystemExit:
                pass

        out = json.loads(capsys.readouterr().out)
        assert out["archived"] is False

    def test_pmids_from_search(self, tmp_path, capsys):
        _make_search_json(tmp_path / "search.json", "pubmed", ["11111", "22222", "33333"])

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", ["media-db-query", "--media-db", str(tmp_path), "--pmids-from-search", str(tmp_path / "search.json")])
            try:
                mq.main()
            except SystemExit:
                pass

        out = json.loads(capsys.readouterr().out)
        assert out["pmid_count"] == 3
        assert out["pmids"] == ["11111", "22222", "33333"]

    def test_text_format(self, tmp_path, capsys):
        _make_paper(tmp_path, "papers/adhd/pmid-99999999-effect")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", ["media-db-query", "--media-db", str(tmp_path), "--check-pmid", "99999999", "--format", "text"])
            try:
                mq.main()
            except SystemExit:
                pass

        out = capsys.readouterr().out
        assert "ARCHIVED" in out
        assert "99999999" in out

    def test_missing_media_db(self, tmp_path, capsys):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", ["media-db-query", "--media-db", str(tmp_path / "nonexistent"), "--list-topics"])
            assert mq.main() == 1

    def test_requires_action(self, capsys):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", ["media-db-query"])
            with pytest.raises(SystemExit):
                mq.main()

    def test_check_epmc_found(self, tmp_path, capsys):
        _make_paper(tmp_path, "papers/adhd/epmc-med-99999999-effect", pmid="99999999", source="europe-pmc")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", ["media-db-query", "--media-db", str(tmp_path), "--check-epmc", "MED:99999999"])
            try:
                mq.main()
            except SystemExit:
                pass

        out = json.loads(capsys.readouterr().out)
        assert out["archived"] is True
        assert len(out["locations"]) == 1

    def test_check_epmc_invalid_format(self, tmp_path, capsys):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", ["media-db-query", "--media-db", str(tmp_path), "--check-epmc", "invalidformat"])
            try:
                mq.main()
            except SystemExit as exc:
                assert exc.code == 1

        captured = capsys.readouterr()
        assert "invalid" in captured.err.lower() or "error" in captured.out.lower()

    def test_read_metadata(self, tmp_path, capsys):
        d = _make_paper(tmp_path, "papers/adhd/pmid-12345-effect", pmid="12345", title="Effect Title")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", ["media-db-query", "--media-db", str(tmp_path), "--read-metadata", str(d)])
            try:
                mq.main()
            except SystemExit:
                pass

        out = json.loads(capsys.readouterr().out)
        assert out["pmid"] == "12345"
        assert out["title"] == "Effect Title"

    def test_search_keyword(self, tmp_path, capsys):
        _make_paper(tmp_path, "papers/adhd/pmid-11111-effect", title="Lisdexamfetamine Study")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", ["media-db-query", "--media-db", str(tmp_path), "--search-keyword", "lisdexamfetamine"])
            try:
                mq.main()
            except SystemExit:
                pass

        out = json.loads(capsys.readouterr().out)
        assert out["match_count"] == 1
        assert out["matches"][0]["match_field"] == "title"

    def test_search_keyword_with_topic_scope(self, tmp_path, capsys):
        _make_paper(tmp_path, "papers/adhd/pmid-11111-effect", title="Lisdexamfetamine ADHD")
        _make_paper(tmp_path, "papers/endo/pmid-22222-endo", title="Lisdexamfetamine Endo")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", [
                "media-db-query", "--media-db", str(tmp_path),
                "--search-keyword", "lisdexamfetamine", "--search-topic", "adhd",
            ])
            try:
                mq.main()
            except SystemExit:
                pass

        out = json.loads(capsys.readouterr().out)
        assert out["match_count"] == 1
        assert "adhd" in out["matches"][0]["folder"]

    def test_topic_papers(self, tmp_path, capsys):
        _make_paper(tmp_path, "papers/adhd/pmid-11111-a", pmid="11111", title="Paper A")
        _make_paper(tmp_path, "papers/adhd/pmid-22222-b", pmid="22222", title="Paper B")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", ["media-db-query", "--media-db", str(tmp_path), "--topic", "adhd"])
            try:
                mq.main()
            except SystemExit:
                pass

        out = json.loads(capsys.readouterr().out)
        assert len(out["papers"]) == 2


# ---------------------------------------------------------------------------
# read_paper_abstract
# ---------------------------------------------------------------------------


class TestReadPaperAbstract:
    def test_existing_abstract(self, tmp_path):
        _make_paper(tmp_path, "papers/adhd/pmid-12345-title", pmid="12345", abstract="Full abstract here.")
        result = mq.read_paper_abstract(tmp_path / "papers" / "adhd" / "pmid-12345-title")
        assert result == "Full abstract here."

    def test_missing_file(self, tmp_path):
        result = mq.read_paper_abstract(tmp_path / "nonexistent")
        assert "not found" in result.lower()


# ---------------------------------------------------------------------------
# recent_papers
# ---------------------------------------------------------------------------


class TestRecentPapers:
    def test_empty_index(self, tmp_path):
        result = mq.recent_papers(tmp_path)
        assert result == []

    def test_returns_most_recent(self, tmp_path):
        _make_paper(tmp_path, "papers/adhd/pmid-11111-a", pmid="11111", title="Older")
        _make_paper(tmp_path, "papers/adhd/pmid-22222-b", pmid="22222", title="Newer")
        index = {
            "searches": [], "fulltext": [], "guidelines": [], "web": [],
            "papers": [
                {"path": "papers/adhd/pmid-11111-a", "identifier": "PMID:11111",
                 "url": "https://pubmed.ncbi.nlm.nih.gov/11111/", "accessed": "2025-01-01"},
                {"path": "papers/adhd/pmid-22222-b", "identifier": "PMID:22222",
                 "url": "https://pubmed.ncbi.nlm.nih.gov/22222/", "accessed": "2026-06-15"},
            ],
        }
        (tmp_path / "index.json").write_text(json.dumps(index))
        result = mq.recent_papers(tmp_path, count=10)
        assert len(result) == 2
        assert result[0]["identifier"] == "PMID:22222"  # newer first
        assert result[1]["identifier"] == "PMID:11111"

    def test_truncated_to_count(self, tmp_path):
        _make_paper(tmp_path, "papers/adhd/pmid-11111-a", pmid="11111")
        _make_paper(tmp_path, "papers/adhd/pmid-22222-b", pmid="22222")
        _make_paper(tmp_path, "papers/adhd/pmid-33333-c", pmid="33333")
        index = {
            "searches": [], "fulltext": [], "guidelines": [], "web": [],
            "papers": [
                {"path": "papers/adhd/pmid-11111-a", "identifier": "PMID:11111",
                 "url": "", "accessed": "2025-01-01"},
                {"path": "papers/adhd/pmid-22222-b", "identifier": "PMID:22222",
                 "url": "", "accessed": "2025-02-01"},
                {"path": "papers/adhd/pmid-33333-c", "identifier": "PMID:33333",
                 "url": "", "accessed": "2025-03-01"},
            ],
        }
        (tmp_path / "index.json").write_text(json.dumps(index))
        result = mq.recent_papers(tmp_path, count=2)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# search_searches
# ---------------------------------------------------------------------------


class TestSearchSearches:
    def test_pubmed_match(self, tmp_path):
        _make_search_json(tmp_path / "searches" / "adhd" / "pubmed-a.json",
                          source="pubmed", pmids=["1"], query="lisdexamfetamine ADHD")
        result = mq.search_searches(tmp_path, "lisdexamfetamine")
        assert len(result) == 1
        assert "pubmed" in result[0]["source"].lower()

    def test_europe_pmc_match(self, tmp_path):
        _make_search_json(tmp_path / "searches" / "depression" / "epmc-a.json",
                          source="epmc", pmids=["2"], query="sexual dysfunction SSRI")
        result = mq.search_searches(tmp_path, "sexual dysfunction")
        assert len(result) == 1
        assert "europe" in result[0]["source"].lower()

    def test_no_match(self, tmp_path):
        _make_search_json(tmp_path / "searches" / "adhd" / "pubmed-a.json",
                          source="pubmed", pmids=["1"], query="ADHD stimulants")
        result = mq.search_searches(tmp_path, "zzz_nonexistent_zzz")
        assert result == []

    def test_scoped_to_topic(self, tmp_path):
        _make_search_json(tmp_path / "searches" / "adhd" / "pubmed-a.json",
                          source="pubmed", pmids=["1"], query="ADHD stimulants")
        _make_search_json(tmp_path / "searches" / "depression" / "epmc-b.json",
                          source="epmc", pmids=["2"], query="depression SSRI")
        result = mq.search_searches(tmp_path, "ADHD", topic="adhd")
        assert len(result) == 1
        result_all = mq.search_searches(tmp_path, "SSRI")
        assert len(result_all) == 1
