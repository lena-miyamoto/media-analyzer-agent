"""Tests for media-db.py — PubMed/Europe PMC archival script."""

import datetime
import io
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

import media_db


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------

class TestSlugify:
    def test_basic_english(self):
        assert media_db.slugify("Hello World") == "hello-world"

    def test_with_special_chars(self):
        assert media_db.slugify("Vitamin D & Calcium (benefits)") == "vitamin-d-calcium-benefits"

    def test_unicode_to_ascii(self):
        result = media_db.slugify("café naïve étude")
        assert result == "cafe-naive-etude"

    def test_german_umlauts(self):
        result = media_db.slugify("Übergewicht und Ernährung")
        assert result == "ubergewicht-und-ernahrung"

    def test_empty_string_fallback(self):
        result = media_db.slugify("")
        assert result == "record"

    def test_only_special_chars_fallback(self):
        result = media_db.slugify("!@#$%")
        assert result == "record"

    def test_custom_fallback(self):
        result = media_db.slugify("!!!", fallback="custom-fb")
        assert result == "custom-fb"

    def test_max_words_truncation(self):
        result = media_db.slugify(
            "one two three four five six seven eight nine ten eleven twelve",
            max_words=5,
        )
        assert result == "one-two-three-four-five"

    def test_max_length_truncation(self):
        result = media_db.slugify("a very long title that exceeds the character limit easily", max_length=25)
        assert len(result) <= 25
        assert result == "a-very-long-title-that-ex"

    def test_max_length_doesnt_end_with_hyphen(self):
        result = media_db.slugify("abcdef-ghijklm-nopqrstuv", max_length=13)
        assert not result.endswith("-")

    def test_max_length_strips_trailing_hyphens(self):
        result = media_db.slugify("a-b", max_length=2)
        assert result == "a" and not result.endswith("-")

    def test_consecutive_special_chars(self):
        result = media_db.slugify("hello---world___test")
        assert result == "hello-world-test"


# ---------------------------------------------------------------------------
# unique_filename
# ---------------------------------------------------------------------------

class TestUniqueFilename:
    def test_no_collision(self, tmp_path):
        result = media_db.unique_filename(tmp_path, "hello", ".json")
        assert result == "hello.json"

    def test_with_collision(self, tmp_path):
        (tmp_path / "hello.json").write_text("existing")
        result = media_db.unique_filename(tmp_path, "hello", ".json")
        assert result == "hello-2.json"

    def test_multiple_collisions(self, tmp_path):
        (tmp_path / "hello.json").write_text("1")
        (tmp_path / "hello-2.json").write_text("2")
        (tmp_path / "hello-3.json").write_text("3")
        result = media_db.unique_filename(tmp_path, "hello", ".json")
        assert result == "hello-4.json"

    def test_with_gap_in_numbers(self, tmp_path):
        (tmp_path / "hello.json").write_text("1")
        (tmp_path / "hello-3.json").write_text("3")
        result = media_db.unique_filename(tmp_path, "hello", ".json")
        assert result == "hello-2.json"

    def test_different_suffix(self, tmp_path):
        (tmp_path / "hello.json").write_text("json")
        result = media_db.unique_filename(tmp_path, "hello", ".txt")
        assert result == "hello.txt"

    def test_numeric_stem(self, tmp_path):
        result = media_db.unique_filename(tmp_path, "123-data", ".json")
        assert result == "123-data.json"


# ---------------------------------------------------------------------------
# dedupe
# ---------------------------------------------------------------------------

class TestDedupe:
    def test_no_duplicates(self):
        assert media_db.dedupe([1, 2, 3]) == [1, 2, 3]

    def test_removes_duplicates_preserves_order(self):
        assert media_db.dedupe([3, 1, 2, 1, 3, 4]) == [3, 1, 2, 4]

    def test_empty_list(self):
        assert media_db.dedupe([]) == []

    def test_single_item(self):
        assert media_db.dedupe([42]) == [42]

    def test_all_duplicates(self):
        assert media_db.dedupe(["a", "a", "a"]) == ["a"]

    def test_strings(self):
        assert media_db.dedupe(["b", "a", "b", "c", "a"]) == ["b", "a", "c"]


# ---------------------------------------------------------------------------
# source_label
# ---------------------------------------------------------------------------

class TestSourceLabel:
    def test_known_sources(self):
        assert media_db.source_label("pubmed") == "PubMed"
        assert media_db.source_label("europe-pmc") == "Europe PMC"
        assert media_db.source_label("google-scholar") == "Google Scholar"
        assert media_db.source_label("doaj") == "Directory of Open Access Journals"
        assert media_db.source_label("open-science-directory") == "Open Science Directory"

    def test_unknown_source_returns_itself(self):
        assert media_db.source_label("some-random-source") == "some-random-source"
        assert media_db.source_label("") == ""


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------

class TestBuildGoogleScholarUrl:
    def test_basic_query(self):
        url = media_db.build_google_scholar_url("endometriosis diet")
        assert "scholar.google.com/scholar" in url
        assert "q=endometriosis+diet" in url or "endometriosis%20diet" in url
        assert "hl=en" in url

    def test_special_characters(self):
        url = media_db.build_google_scholar_url('"vitamin D" calcium')
        assert "scholar.google.com" in url


class TestBuildDoajUrl:
    def test_basic_query(self):
        url = media_db.build_doaj_url("endometriosis")
        assert "doaj.org/search/articles" in url
        assert "ref=homepage" in url or "homepage" in url

    def test_url_contains_json_source(self):
        url = media_db.build_doaj_url("endometriosis diet")
        assert "source=" in url


# ---------------------------------------------------------------------------
# build_common_params
# ---------------------------------------------------------------------------

class TestBuildCommonParams:
    def test_defaults(self):
        args = mock.Mock(email=None)
        params = media_db.build_common_params(args)
        assert params["db"] == "pubmed"
        assert params["tool"] == "media-db"
        assert "email" not in params

    def test_with_email(self):
        args = mock.Mock(email="researcher@example.com")
        params = media_db.build_common_params(args)
        assert params["email"] == "researcher@example.com"

    def test_with_empty_email(self):
        args = mock.Mock(email="")
        params = media_db.build_common_params(args)
        assert "email" not in params


# ---------------------------------------------------------------------------
# europe_pmc_article_url
# ---------------------------------------------------------------------------

class TestEuropePmcArticleUrl:
    def test_med_source(self):
        url = media_db.europe_pmc_article_url("MED", "35350465")
        assert url == "https://europepmc.org/article/MED/35350465"

    def test_ppr_source(self):
        url = media_db.europe_pmc_article_url("PPR", "12345")
        assert url == "https://europepmc.org/article/PPR/12345"


# ---------------------------------------------------------------------------
# parse_europe_pmc_record
# ---------------------------------------------------------------------------

class TestParseEuropePmcRecord:
    def test_valid_med_record(self):
        source, record_id = media_db.parse_europe_pmc_record("MED:35350465")
        assert source == "MED"
        assert record_id == "35350465"

    def test_valid_ppr_record(self):
        source, record_id = media_db.parse_europe_pmc_record("PPR:12345")
        assert source == "PPR"
        assert record_id == "12345"

    def test_missing_colon_raises(self):
        with pytest.raises(ValueError, match="invalid Europe PMC record spec"):
            media_db.parse_europe_pmc_record("MED35350465")

    def test_empty_source_raises(self):
        with pytest.raises(ValueError, match="invalid Europe PMC record spec"):
            media_db.parse_europe_pmc_record(":35350465")

    def test_empty_id_raises(self):
        with pytest.raises(ValueError, match="invalid Europe PMC record spec"):
            media_db.parse_europe_pmc_record("MED:")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            media_db.parse_europe_pmc_record("")


# ---------------------------------------------------------------------------
# query_from_search_json
# ---------------------------------------------------------------------------

class TestQueryFromSearchJson:
    def test_pubmed_format(self, tmp_path):
        data = {
            "header": {"type": "esearch"},
            "esearchresult": {
                "querytranslation": "endometriosis[MeSH] AND diet[MeSH]",
                "idlist": ["123", "456"],
            },
        }
        path = tmp_path / "search.json"
        path.write_text(json.dumps(data))
        result = media_db.query_from_search_json(path)
        assert result == "endometriosis[MeSH] AND diet[MeSH]"

    def test_pubmed_missing_querytranslation(self, tmp_path):
        data = {
            "header": {"type": "esearch"},
            "esearchresult": {"idlist": ["123"]},
        }
        path = tmp_path / "search.json"
        path.write_text(json.dumps(data))
        result = media_db.query_from_search_json(path)
        assert "Query unavailable" in result

    def test_europe_pmc_format(self, tmp_path):
        data = {
            "request": {"queryString": "endometriosis AND diet"},
            "resultList": {"result": []},
        }
        path = tmp_path / "search.json"
        path.write_text(json.dumps(data))
        result = media_db.query_from_search_json(path)
        assert result == "endometriosis AND diet"

    def test_europe_pmc_alternative_query_field(self, tmp_path):
        data = {
            "request": {"query": "endometriosis diet"},
            "resultList": {"result": []},
        }
        path = tmp_path / "search.json"
        path.write_text(json.dumps(data))
        result = media_db.query_from_search_json(path)
        assert result == "endometriosis diet"

    def test_unknown_format(self, tmp_path):
        data = {"some_other_field": "value"}
        path = tmp_path / "search.json"
        path.write_text(json.dumps(data))
        result = media_db.query_from_search_json(path)
        assert "Query unavailable" in result


# ---------------------------------------------------------------------------
# source_from_search_json
# ---------------------------------------------------------------------------

class TestSourceFromSearchJson:
    def test_pubmed(self, tmp_path):
        data = {"esearchresult": {"idlist": ["1"]}}
        path = tmp_path / "search.json"
        path.write_text(json.dumps(data))
        assert media_db.source_from_search_json(path) == "PubMed"

    def test_europe_pmc(self, tmp_path):
        data = {
            "request": {"queryString": "test"},
            "resultList": {"result": []},
        }
        path = tmp_path / "search.json"
        path.write_text(json.dumps(data))
        assert media_db.source_from_search_json(path) == "Europe PMC"

    def test_europe_pmc_null_resultlist(self, tmp_path):
        data = {
            "request": {"queryString": "test"},
            "resultList": None,
        }
        path = tmp_path / "search.json"
        path.write_text(json.dumps(data))
        # resultList IS None, but resultList is not None is False;
        # the condition checks: request AND resultList is not None.
        # Since resultList IS None, this won't match Europe PMC format
        result = media_db.source_from_search_json(path)
        # Falls through to Unknown since both PubMed and EPMC checks fail
        assert result == "Unknown"

    def test_unknown(self, tmp_path):
        data = {"something": "else"}
        path = tmp_path / "search.json"
        path.write_text(json.dumps(data))
        assert media_db.source_from_search_json(path) == "Unknown"


# ---------------------------------------------------------------------------
# default_paper_entry
# ---------------------------------------------------------------------------

class TestDefaultPaperEntry:
    def test_pubmed_single_uid(self, tmp_path):
        data = {"result": {"uids": ["12345678"]}}
        path = tmp_path / "metadata.json"
        path.write_text(json.dumps(data))
        identifier, url = media_db.default_paper_entry(path)
        assert identifier == "PMID:12345678"
        assert url == "https://pubmed.ncbi.nlm.nih.gov/12345678/"

    def test_pubmed_multiple_uids(self, tmp_path):
        data = {"result": {"uids": ["111", "222"]}}
        path = tmp_path / "metadata.json"
        path.write_text(json.dumps(data))
        identifier, url = media_db.default_paper_entry(path)
        assert identifier == "unknown"
        assert "unavailable" in url

    def test_europe_pmc_record(self, tmp_path):
        data = {
            "resultList": {
                "result": [
                    {"source": "MED", "id": "35350465", "title": "Test"}
                ]
            }
        }
        path = tmp_path / "metadata.json"
        path.write_text(json.dumps(data))
        identifier, url = media_db.default_paper_entry(path)
        assert identifier == "MED:35350465"
        assert "europepmc.org/article/MED/35350465" in url

    def test_europe_pmc_fallback_to_pmid(self, tmp_path):
        data = {
            "resultList": {
                "result": [
                    {"source": "MED", "pmid": "12345678"}
                ]
            }
        }
        path = tmp_path / "metadata.json"
        path.write_text(json.dumps(data))
        identifier, url = media_db.default_paper_entry(path)
        # id missing, falls back to pmid
        assert identifier == "MED:12345678"

    def test_unknown_format(self, tmp_path):
        data = {"something": "unexpected"}
        path = tmp_path / "metadata.json"
        path.write_text(json.dumps(data))
        identifier, url = media_db.default_paper_entry(path)
        assert identifier == "unknown"
        assert "unavailable" in url


# ---------------------------------------------------------------------------
# ensure_media_db_structure
# ---------------------------------------------------------------------------

class TestEnsureMedDbStructure:
    def test_creates_all_dirs(self, tmp_path):
        media_db.ensure_media_db_structure(tmp_path)
        for name in ("searches", "papers", "fulltext", "guidelines", "web"):
            assert (tmp_path / name).is_dir()

    def test_idempotent(self, tmp_path):
        media_db.ensure_media_db_structure(tmp_path)
        media_db.ensure_media_db_structure(tmp_path)
        for name in ("searches", "papers", "fulltext", "guidelines", "web"):
            assert (tmp_path / name).is_dir()

    def test_partial_existing(self, tmp_path):
        (tmp_path / "searches").mkdir()
        (tmp_path / "papers").mkdir()
        media_db.ensure_media_db_structure(tmp_path)
        for name in ("searches", "papers", "fulltext", "guidelines", "web"):
            assert (tmp_path / name).is_dir()


# ---------------------------------------------------------------------------
# load_existing_index_entries
# ---------------------------------------------------------------------------

class TestLoadExistingIndexEntries:
    def test_missing_index(self, tmp_path):
        result = media_db.load_existing_index_entries(tmp_path / "index.json")
        assert result == ({}, {}, {}, {}, {})

    def test_empty_index(self, tmp_path):
        index = tmp_path / "index.json"
        index.write_text(json.dumps({"searches": [], "papers": []}))
        searches, papers, fulltexts, guidelines, web = media_db.load_existing_index_entries(index)
        assert searches == {}
        assert papers == {}

    def test_parses_search_entry(self, tmp_path):
        index = tmp_path / "index.json"
        index.write_text(json.dumps({
            "searches": [
                {"path": "searches/endometriosis/pubmed-diet.json", "source": "PubMed", "query": "endometriosis AND diet", "purpose": "Review dietary interventions", "accessed": "2026-06-01"}
            ]
        }))
        searches, papers, fulltexts, guidelines, web = media_db.load_existing_index_entries(index)
        key = "searches/endometriosis/pubmed-diet.json"
        assert key in searches
        assert searches[key]["source"] == "PubMed"
        assert searches[key]["query"] == "endometriosis AND diet"
        assert searches[key]["purpose"] == "Review dietary interventions"
        assert searches[key]["accessed"] == "2026-06-01"

    def test_parses_paper_entry(self, tmp_path):
        index = tmp_path / "index.json"
        index.write_text(json.dumps({
            "papers": [
                {"path": "papers/endometriosis/pmid-12345678-title", "identifier": "PMID:12345678", "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/", "purpose": "Endometriosis diet review", "accessed": "2026-06-01"}
            ]
        }))
        searches, papers, fulltexts, guidelines, web = media_db.load_existing_index_entries(index)
        key = "papers/endometriosis/pmid-12345678-title"
        assert key in papers
        assert papers[key]["identifier"] == "PMID:12345678"
        assert papers[key]["purpose"] == "Endometriosis diet review"

    def test_parses_fulltext_entry(self, tmp_path):
        index = tmp_path / "index.json"
        index.write_text(json.dumps({
            "fulltext": [
                {"path": "fulltext/endometriosis/pmid-12345678-title", "identifier": "PMID:12345678", "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/", "purpose": "Full review", "accessed": "2026-06-01"}
            ]
        }))
        searches, papers, fulltexts, guidelines, web = media_db.load_existing_index_entries(index)
        key = "fulltext/endometriosis/pmid-12345678-title"
        assert key in fulltexts
        assert fulltexts[key]["purpose"] == "Full review"

    def test_parses_guideline_entry(self, tmp_path):
        index = tmp_path / "index.json"
        index.write_text(json.dumps({
            "guidelines": [
                {"path": "guidelines/endometriosis/eshre-guideline", "source": "ESHRE", "url": "https://eshre.eu/", "purpose": "Clinical guideline", "accessed": "2026-06-01"}
            ]
        }))
        searches, papers, fulltexts, guidelines, web = media_db.load_existing_index_entries(index)
        key = "guidelines/endometriosis/eshre-guideline"
        assert key in guidelines
        assert guidelines[key]["source"] == "ESHRE"

    def test_parses_web_entry(self, tmp_path):
        index = tmp_path / "index.json"
        index.write_text(json.dumps({
            "web": [
                {"path": "web/endometriosis/google-scholar-search.html", "url": "https://scholar.google.com/scholar?q=test", "purpose": "Test search", "accessed": "2026-06-01"}
            ]
        }))
        searches, papers, fulltexts, guidelines, web = media_db.load_existing_index_entries(index)
        key = "web/endometriosis/google-scholar-search.html"
        assert key in web
        assert web[key]["url"] == "https://scholar.google.com/scholar?q=test"

    def test_ignores_unknown_keys(self, tmp_path):
        index = tmp_path / "index.json"
        index.write_text(json.dumps({
            "some_other_key": [
                {"path": "papers/something/"}
            ],
            "papers": []
        }))
        searches, papers, fulltexts, guidelines, web = media_db.load_existing_index_entries(index)
        assert "papers/something" not in papers
        assert papers == {}

    def test_handles_invalid_json(self, tmp_path):
        index = tmp_path / "index.json"
        index.write_text("not valid json {{{")
        result = media_db.load_existing_index_entries(index)
        assert result == ({}, {}, {}, {}, {})

    def test_pipe_in_cell_no_longer_a_problem(self, tmp_path):
        """Pipes in cell values are trivially handled in JSON — no escaping issues."""
        index = tmp_path / "index.json"
        index.write_text(json.dumps({
            "papers": [
                {"path": "papers/topic/pmid-12345-test", "identifier": "PMID:12345", "url": "https://example.com", "purpose": "Purpose | with pipe", "accessed": "2026-06-01"}
            ]
        }))
        searches, papers, fulltexts, guidelines, web = media_db.load_existing_index_entries(index)
        # JSON handles pipes natively — no parsing ambiguity
        key = "papers/topic/pmid-12345-test"
        assert key in papers
        assert papers[key]["purpose"] == "Purpose | with pipe"


# ---------------------------------------------------------------------------
# collect_index_data
# ---------------------------------------------------------------------------

class TestCollectIndexData:
    def test_empty_media_db(self, tmp_path):
        media_db.ensure_media_db_structure(tmp_path)
        searches, papers, fulltexts, guidelines, web = media_db.collect_index_data(tmp_path)
        assert searches == []
        assert papers == []
        assert fulltexts == []
        assert guidelines == []
        assert web == []

    def test_collects_search_json(self, tmp_path):
        topic_dir = tmp_path / "searches" / "endometriosis"
        topic_dir.mkdir(parents=True)
        search_data = json.dumps({"esearchresult": {"querytranslation": "test", "idlist": ["1"]}})
        (topic_dir / "pubmed-test.json").write_text(search_data)
        searches, papers, fulltexts, guidelines, web = media_db.collect_index_data(tmp_path)
        assert len(searches) == 1
        assert searches[0]["source"] == "PubMed"
        assert "searches/endometriosis/pubmed-test.json" in searches[0]["path"]
        today = datetime.date.today().isoformat()
        assert searches[0]["accessed"] == today

    def test_collects_paper_metadata(self, tmp_path):
        paper_dir = tmp_path / "papers" / "endometriosis" / "pmid-12345-test"
        paper_dir.mkdir(parents=True)
        metadata = {"result": {"uids": ["12345"]}}
        (paper_dir / "metadata.json").write_text(json.dumps(metadata))
        searches, papers, fulltexts, guidelines, web = media_db.collect_index_data(tmp_path)
        assert len(papers) == 1
        assert papers[0]["identifier"] == "PMID:12345"

    def test_collects_fulltext_metadata(self, tmp_path):
        ft_dir = tmp_path / "fulltext" / "endometriosis" / "pmid-12345-test"
        ft_dir.mkdir(parents=True)
        metadata = {"result": {"uids": ["12345"]}}
        (ft_dir / "metadata.json").write_text(json.dumps(metadata))
        searches, papers, fulltexts, guidelines, web = media_db.collect_index_data(tmp_path)
        assert len(fulltexts) == 1
        assert fulltexts[0]["identifier"] == "PMID:12345"

    def test_collects_guidelines(self, tmp_path):
        gl_dir = tmp_path / "guidelines" / "endometriosis" / "eshre-guideline"
        gl_dir.mkdir(parents=True)
        (gl_dir / "source.en.md").write_text("---\ntitle: Test\n---\n\nContent")
        searches, papers, fulltexts, guidelines, web = media_db.collect_index_data(tmp_path)
        assert len(guidelines) == 1

    def test_guideline_deduplication_multilingual(self, tmp_path):
        """Guideline folder with multiple language sources should only appear once."""
        gl_dir = tmp_path / "guidelines" / "endometriosis" / "eshre-guideline"
        gl_dir.mkdir(parents=True)
        (gl_dir / "source.en.md").write_text("---\ntitle: EN\n---\n\nContent")
        (gl_dir / "source.de.md").write_text("---\ntitle: DE\n---\n\nInhalt")
        searches, papers, fulltexts, guidelines, web = media_db.collect_index_data(tmp_path)
        assert len(guidelines) == 1

    def test_collects_web_sources(self, tmp_path):
        web_dir = tmp_path / "web" / "endometriosis"
        web_dir.mkdir(parents=True)
        (web_dir / "test.html").write_text("<html><body>test</body></html>")
        searches, papers, fulltexts, guidelines, web = media_db.collect_index_data(tmp_path)
        assert len(web) == 1

    def test_missing_dirs_no_error(self, tmp_path):
        """Should handle missing directory trees gracefully."""
        searches, papers, fulltexts, guidelines, web = media_db.collect_index_data(tmp_path)
        assert searches == []
        assert papers == []
        assert fulltexts == []
        assert guidelines == []
        assert web == []


# ---------------------------------------------------------------------------
# sync_index
# ---------------------------------------------------------------------------

class TestSyncIndex:
    def test_creates_index_from_scratch(self, tmp_path):
        media_db.ensure_media_db_structure(tmp_path)
        # Add a search file
        searches_dir = tmp_path / "searches" / "endometriosis"
        searches_dir.mkdir(parents=True)
        (searches_dir / "pubmed-test.json").write_text(
            json.dumps({"esearchresult": {"querytranslation": "test", "idlist": ["1"]}})
        )
        media_db.sync_index(tmp_path)
        index = tmp_path / "index.json"
        assert index.is_file()
        data = json.loads(index.read_text())
        assert "searches" in data
        assert "papers" in data
        assert "fulltext" in data
        assert "guidelines" in data
        assert "web" in data
        assert any("pubmed-test.json" in s["path"] for s in data["searches"])

    def test_preserves_existing_entry_metadata(self, tmp_path):
        media_db.ensure_media_db_structure(tmp_path)
        # Create a search file
        searches_dir = tmp_path / "searches" / "endometriosis"
        searches_dir.mkdir(parents=True)
        (searches_dir / "pubmed-test.json").write_text(
            json.dumps({"esearchresult": {"querytranslation": "test", "idlist": ["1"]}})
        )
        # First sync to create initial index
        media_db.sync_index(tmp_path)
        # Second sync with update to preserve custom purpose
        media_db.sync_index(
            tmp_path,
            search_updates={
                "searches/endometriosis/pubmed-test.json": {
                    "source": "PubMed",
                    "query": "endometriosis AND diet",
                    "purpose": "Custom purpose for review",
                    "accessed": "2026-01-15",
                }
            },
        )
        data = json.loads((tmp_path / "index.json").read_text())
        search = next(s for s in data["searches"] if "pubmed-test.json" in s["path"])
        assert search["purpose"] == "Custom purpose for review"
        assert search["accessed"] == "2026-01-15"

    def test_includes_paper_entries(self, tmp_path):
        media_db.ensure_media_db_structure(tmp_path)
        paper_dir = tmp_path / "papers" / "endometriosis" / "pmid-12345-test"
        paper_dir.mkdir(parents=True)
        (paper_dir / "metadata.json").write_text(
            json.dumps({"result": {"uids": ["12345"]}})
        )
        media_db.sync_index(tmp_path)
        data = json.loads((tmp_path / "index.json").read_text())
        assert any("pmid-12345-test" in p["path"] for p in data["papers"])
        assert any("PMID:12345" in p["identifier"] for p in data["papers"])

    def test_includes_web_entries(self, tmp_path):
        media_db.ensure_media_db_structure(tmp_path)
        web_dir = tmp_path / "web" / "endometriosis"
        web_dir.mkdir(parents=True)
        (web_dir / "google-scholar-test.html").write_text("<html></html>")
        media_db.sync_index(tmp_path)
        data = json.loads((tmp_path / "index.json").read_text())
        assert any("google-scholar-test.html" in w["path"] for w in data["web"])

    def test_index_ends_with_newline(self, tmp_path):
        media_db.ensure_media_db_structure(tmp_path)
        media_db.sync_index(tmp_path)
        content = (tmp_path / "index.json").read_text()
        assert content.endswith("\n")

    def test_round_trip_preserves_custom_metadata(self, tmp_path):
        """After sync_index writes custom metadata to index.json, a second
        sync_index (without explicit updates) must preserve it by reading
        it back from the file."""
        media_db.ensure_media_db_structure(tmp_path)
        searches_dir = tmp_path / "searches" / "endometriosis"
        searches_dir.mkdir(parents=True)
        (searches_dir / "pubmed-test.json").write_text(
            json.dumps({"esearchresult": {"querytranslation": "test", "idlist": ["1"]}})
        )
        # First sync with explicit custom metadata
        media_db.sync_index(
            tmp_path,
            search_updates={
                "searches/endometriosis/pubmed-test.json": {
                    "source": "PubMed",
                    "query": "endometriosis AND diet",
                    "purpose": "Custom purpose that must survive",
                    "accessed": "2026-01-15",
                }
            },
        )
        # Second sync WITHOUT updates — metadata should be recovered from index.json
        media_db.sync_index(tmp_path)
        data = json.loads((tmp_path / "index.json").read_text())
        search = next(s for s in data["searches"] if "pubmed-test.json" in s["path"])
        assert search["purpose"] == "Custom purpose that must survive"
        assert search["accessed"] == "2026-01-15"

    def test_includes_guideline_entries(self, tmp_path):
        media_db.ensure_media_db_structure(tmp_path)
        gl_dir = tmp_path / "guidelines" / "endometriosis" / "eshre-guideline"
        gl_dir.mkdir(parents=True)
        (gl_dir / "source.en.md").write_text("---\ntitle: Test\n---\n\nContent")
        media_db.sync_index(tmp_path)
        data = json.loads((tmp_path / "index.json").read_text())
        assert any("eshre-guideline" in g["path"] for g in data["guidelines"])

    def test_preserves_guideline_custom_metadata(self, tmp_path):
        media_db.ensure_media_db_structure(tmp_path)
        gl_dir = tmp_path / "guidelines" / "endometriosis" / "eshre-guideline"
        gl_dir.mkdir(parents=True)
        (gl_dir / "source.en.md").write_text("---\ntitle: Test\n---\n\nContent")
        media_db.sync_index(
            tmp_path,
            guideline_updates={
                "guidelines/endometriosis/eshre-guideline": {
                    "source": "ESHRE",
                    "url": "https://eshre.eu/guideline",
                    "purpose": "Clinical practice guideline",
                    "accessed": "2026-01-15",
                }
            },
        )
        data = json.loads((tmp_path / "index.json").read_text())
        gl = next(g for g in data["guidelines"] if "eshre-guideline" in g["path"])
        assert gl["source"] == "ESHRE"
        assert "eshre.eu" in gl["url"]
        assert gl["purpose"] == "Clinical practice guideline"
        assert gl["accessed"] == "2026-01-15"

    def test_preserves_web_custom_metadata(self, tmp_path):
        media_db.ensure_media_db_structure(tmp_path)
        web_dir = tmp_path / "web" / "endometriosis"
        web_dir.mkdir(parents=True)
        (web_dir / "google-scholar-test.html").write_text("<html></html>")
        media_db.sync_index(
            tmp_path,
            web_updates={
                "web/endometriosis/google-scholar-test.html": {
                    "url": "https://scholar.google.com/scholar?q=test",
                    "purpose": "Custom web search",
                    "accessed": "2026-02-01",
                }
            },
        )
        data = json.loads((tmp_path / "index.json").read_text())
        web = next(w for w in data["web"] if "google-scholar-test.html" in w["path"])
        assert web["purpose"] == "Custom web search"
        assert web["accessed"] == "2026-02-01"


# ---------------------------------------------------------------------------
# archive_web_query
# ---------------------------------------------------------------------------

class TestArchiveWebQuery:
    def test_google_scholar_creates_html(self, tmp_path):
        args = mock.Mock(
            source="google-scholar",
            query="endometriosis AND diet",
            search_slug="test-search",
        )
        media_db.ensure_media_db_structure(tmp_path)
        web_file, target_url = media_db.archive_web_query(args, tmp_path, "endometriosis")
        assert web_file.exists()
        content = web_file.read_text()
        assert "<!doctype html>" in content.lower()
        assert "endometriosis AND diet" in html_unescape(content)
        assert "Google Scholar" in content
        assert "scholar.google.com" in target_url

    def test_source_without_query_builder(self, tmp_path):
        args = mock.Mock(
            source="open-science-directory",
            query="endometriosis",
            search_slug="test-search",
        )
        media_db.ensure_media_db_structure(tmp_path)
        web_file, target_url = media_db.archive_web_query(args, tmp_path, "endometriosis")
        assert web_file.exists()
        content = web_file.read_text()
        assert "does not expose a stable public query URL" in content
        assert "Open Science Directory" in content

    def test_falls_back_slug_when_not_given(self, tmp_path):
        args = mock.Mock(
            source="google-scholar",
            query="endometriosis diet research",
            search_slug=None,
        )
        media_db.ensure_media_db_structure(tmp_path)
        web_file, target_url = media_db.archive_web_query(args, tmp_path, "endometriosis")
        assert web_file.exists()
        assert "google-scholar" in web_file.name

    def test_unique_filename_on_collision(self, tmp_path):
        args = mock.Mock(
            source="google-scholar",
            query="test",
            search_slug="test-search",
        )
        media_db.ensure_media_db_structure(tmp_path)
        web_dir = tmp_path / "web" / "endometriosis"
        web_dir.mkdir(parents=True)
        (web_dir / "google-scholar-test-search.html").write_text("existing")
        web_file, _ = media_db.archive_web_query(args, tmp_path, "endometriosis")
        assert "google-scholar-test-search-2.html" == web_file.name


def html_unescape(s):
    import html
    return html.unescape(s)


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------

class TestParseArgs:
    def test_minimal_query(self):
        with mock.patch.object(sys, "argv", ["media-db.py", "--query", "endometriosis"]):
            args = media_db.parse_args()
        assert args.query == "endometriosis"
        assert args.source == "pubmed"
        assert args.topic == "uncategorized"

    def test_query_required_without_pmid(self):
        with mock.patch.object(sys, "argv", ["media-db.py"]):
            with pytest.raises(SystemExit):
                media_db.parse_args()

    def test_pmid_only(self):
        with mock.patch.object(sys, "argv", ["media-db.py", "--pmid", "12345678"]):
            args = media_db.parse_args()
        assert args.pmid == ["12345678"]

    def test_multiple_pmids(self):
        with mock.patch.object(sys, "argv", ["media-db.py", "--pmid", "1", "--pmid", "2"]):
            args = media_db.parse_args()
        assert args.pmid == ["1", "2"]

    def test_source_validation_pmid(self):
        with mock.patch.object(sys, "argv", ["media-db.py", "--source", "europe-pmc", "--pmid", "1"]):
            with pytest.raises(SystemExit):
                media_db.parse_args()

    def test_source_validation_epmc(self):
        with mock.patch.object(sys, "argv", ["media-db.py", "--source", "pubmed", "--epmc-record", "MED:1"]):
            with pytest.raises(SystemExit):
                media_db.parse_args()

    def test_archive_first_without_query(self):
        with mock.patch.object(sys, "argv", ["media-db.py", "--pmid", "1", "--archive-first", "5"]):
            with pytest.raises(SystemExit):
                media_db.parse_args()

    def test_archive_first_negative(self):
        with mock.patch.object(sys, "argv", ["media-db.py", "--query", "test", "--archive-first", "-1"]):
            with pytest.raises(SystemExit):
                media_db.parse_args()

    def test_archive_first_web_source(self):
        with mock.patch.object(sys, "argv", ["media-db.py", "--source", "google-scholar", "--query", "test", "--archive-first", "5"]):
            with pytest.raises(SystemExit):
                media_db.parse_args()

    def test_retmax_minimum(self):
        with mock.patch.object(sys, "argv", ["media-db.py", "--query", "test", "--retmax", "0"]):
            with pytest.raises(SystemExit):
                media_db.parse_args()

    def test_topic_and_topic_slug(self):
        with mock.patch.object(sys, "argv", ["media-db.py", "--query", "test", "--topic", "Endometriosis", "--topic-slug", "endo"]):
            args = media_db.parse_args()
        assert args.topic == "Endometriosis"
        assert args.topic_slug == "endo"

    def test_migrate_mode(self):
        with mock.patch.object(sys, "argv", ["media-db.py", "--migrate"]):
            args = media_db.parse_args()
        assert args.migrate is True

    def test_migrate_needs_no_query(self):
        """--migrate should not require --query or --pmid."""
        with mock.patch.object(sys, "argv", ["media-db.py", "--migrate"]):
            args = media_db.parse_args()
        assert args.migrate is True

    def test_default_values(self):
        with mock.patch.object(sys, "argv", ["media-db.py", "--query", "test"]):
            args = media_db.parse_args()
        assert args.retmax == 20
        assert args.delay == 0.34
        assert args.media_db == "media-db"

    def test_europe_pmc_source_with_epmc_record(self):
        with mock.patch.object(sys, "argv", ["media-db.py", "--source", "europe-pmc", "--epmc-record", "MED:35350465"]):
            args = media_db.parse_args()
        assert args.epmc_record == ["MED:35350465"]

    def test_epmc_record_requires_europe_pmc_source(self):
        with mock.patch.object(sys, "argv", ["media-db.py", "--source", "doaj", "--epmc-record", "MED:1"]):
            with pytest.raises(SystemExit):
                media_db.parse_args()


class TestValidateTopicSlug:
    def test_accepts_kebab_case(self):
        assert media_db.validate_topic_slug("weight-loss") == "weight-loss"

    def test_rejects_path_separators(self):
        with pytest.raises(ValueError):
            media_db.validate_topic_slug("../adhd")

    def test_rejects_non_slug_text(self):
        with pytest.raises(ValueError):
            media_db.validate_topic_slug("ADHD")


# ---------------------------------------------------------------------------
# migrate_flat_to_topic
# ---------------------------------------------------------------------------

class TestMigrateFlatToTopic:
    def test_migrate_papers(self, tmp_path):
        media_db.ensure_media_db_structure(tmp_path)
        # Create old flat structure
        old_meta = tmp_path / "metadata"
        old_meta.mkdir()
        old_abs = tmp_path / "abstracts"
        old_abs.mkdir()
        (old_meta / "pmid-12345-test.json").write_text('{"result":{"uids":["12345"]}}')
        (old_abs / "pmid-12345-test.txt").write_text("Abstract content")

        exit_code = media_db.migrate_flat_to_topic(tmp_path, dry_run=False)
        assert exit_code == 0

        dest = tmp_path / "papers" / "_migrated" / "pmid-12345-test"
        assert dest.is_dir()
        assert (dest / "metadata.json").is_file()
        assert (dest / "abstract.txt").is_file()
        assert (dest / "abstract.txt").read_text() == "Abstract content"

    def test_migrate_papers_missing_abstract(self, tmp_path):
        media_db.ensure_media_db_structure(tmp_path)
        old_meta = tmp_path / "metadata"
        old_meta.mkdir()
        (tmp_path / "abstracts").mkdir()
        (old_meta / "pmid-12345-test.json").write_text('{"result":{"uids":["12345"]}}')

        media_db.migrate_flat_to_topic(tmp_path)
        dest = tmp_path / "papers" / "_migrated" / "pmid-12345-test"
        assert (dest / "abstract.txt").read_text() == "Abstract not found in old flat abstracts/ directory.\n"

    def test_dry_run_makes_no_changes(self, tmp_path):
        media_db.ensure_media_db_structure(tmp_path)
        old_meta = tmp_path / "metadata"
        old_meta.mkdir()
        (tmp_path / "abstracts").mkdir()
        (old_meta / "pmid-12345-test.json").write_text('{"result":{"uids":["12345"]}}')

        media_db.migrate_flat_to_topic(tmp_path, dry_run=True)
        dest = tmp_path / "papers" / "_migrated" / "pmid-12345-test"
        assert not dest.exists()

    def test_migrate_searches(self, tmp_path):
        media_db.ensure_media_db_structure(tmp_path)
        # ensure_media_db_structure already creates searches/; place old-style files there
        old_searches = tmp_path / "searches"
        (old_searches / "s2026-test.json").write_text('{"esearchresult":{"idlist":["1"]}}')

        media_db.migrate_flat_to_topic(tmp_path)
        dest = tmp_path / "searches" / "_migrated" / "s2026-test.json"
        assert dest.is_file()

    def test_migrate_web(self, tmp_path):
        media_db.ensure_media_db_structure(tmp_path)
        # ensure_media_db_structure already creates web/; place old-style files there
        old_web = tmp_path / "web"
        (old_web / "test-page.html").write_text("<html></html>")

        media_db.migrate_flat_to_topic(tmp_path)
        dest = tmp_path / "web" / "_migrated" / "test-page.html"
        assert dest.is_file()

    def test_skips_already_migrated(self, tmp_path):
        media_db.ensure_media_db_structure(tmp_path)
        old_meta = tmp_path / "metadata"
        old_meta.mkdir()
        (tmp_path / "abstracts").mkdir()
        (old_meta / "pmid-12345-test.json").write_text('{"result":{"uids":["12345"]}}')

        # Pre-create the destination
        dest_dir = tmp_path / "papers" / "_migrated" / "pmid-12345-test"
        dest_dir.mkdir(parents=True)
        (dest_dir / "metadata.json").write_text("already migrated")

        media_db.migrate_flat_to_topic(tmp_path)
        assert (dest_dir / "metadata.json").read_text() == "already migrated"

    def test_migrate_empty_dirs(self, tmp_path):
        """Migration of empty directories should be a no-op."""
        media_db.ensure_media_db_structure(tmp_path)
        exit_code = media_db.migrate_flat_to_topic(tmp_path)
        assert exit_code == 0

    def test_copy_size_mismatch_is_error(self, tmp_path, monkeypatch):
        media_db.ensure_media_db_structure(tmp_path)
        old_meta = tmp_path / "metadata"
        old_meta.mkdir()
        (tmp_path / "abstracts").mkdir()
        (old_meta / "pmid-12345-test.json").write_text('{"result":{"uids":["12345"]}}')

        def fake_copy(source, destination):
            Path(destination).write_text("x")

        monkeypatch.setattr(media_db.shutil, "copy2", fake_copy)

        assert media_db.migrate_flat_to_topic(tmp_path) == 1


# ---------------------------------------------------------------------------
# WEB_SOURCE_SPECS static data
# ---------------------------------------------------------------------------

class TestWebSourceSpecs:
    def test_known_sources_present(self):
        for key in ("google-scholar", "doaj", "open-science-directory"):
            assert key in media_db.WEB_SOURCE_SPECS

    def test_google_scholar_has_query_builder(self):
        spec = media_db.WEB_SOURCE_SPECS["google-scholar"]
        assert "query_url_builder" in spec
        assert callable(spec["query_url_builder"])

    def test_open_science_directory_no_query_builder(self):
        spec = media_db.WEB_SOURCE_SPECS["open-science-directory"]
        assert "query_url_builder" not in spec


# ---------------------------------------------------------------------------
# save_text
# ---------------------------------------------------------------------------

class TestSaveText:
    def test_writes_utf8(self, tmp_path):
        path = tmp_path / "test.txt"
        media_db.save_text(path, "héllo wörld")
        assert path.read_text(encoding="utf-8") == "héllo wörld"

    def test_overwrites_existing(self, tmp_path):
        path = tmp_path / "test.txt"
        path.write_text("old content")
        media_db.save_text(path, "new content")
        assert path.read_text(encoding="utf-8") == "new content"


# ---------------------------------------------------------------------------
# Integration-level tests (main with mocked HTTP)
# ---------------------------------------------------------------------------

class TestMainIntegration:
    """Test main() with mocked network calls."""

    def test_migrate_mode(self, tmp_path, capsys, monkeypatch):
        media_db_path = tmp_path / "media-db"
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(sys, "argv", ["media-db.py", "--migrate", "--media-db", str(media_db_path)]):
            exit_code = media_db.main()
        assert exit_code == 0

    def test_migrate_dry_run(self, tmp_path, capsys, monkeypatch):
        media_db_path = tmp_path / "media-db"
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(sys, "argv", ["media-db.py", "--migrate-dry-run", "--media-db", str(media_db_path)]):
            exit_code = media_db.main()
        assert exit_code == 0

    def test_web_query_flow(self, tmp_path, monkeypatch):
        media_db_path = tmp_path / "media-db"
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(sys, "argv", [
            "media-db.py",
            "--source", "google-scholar",
            "--query", "endometriosis AND diet",
            "--search-slug", "test-search",
            "--topic", "endometriosis",
            "--media-db", str(media_db_path),
        ]):
            exit_code = media_db.main()
        assert exit_code == 0
        index = media_db_path / "index.json"
        assert index.is_file()
        data = json.loads(index.read_text())
        assert any("test-search" in w["path"] for w in data["web"])
        # REGRESSION: the web query URL must appear in the index —
        # the old positional-arg bug would lose it and show
        # "URL unavailable; review and refine." instead.
        assert any("scholar.google.com" in w["url"] for w in data["web"])

    def test_web_url_survives_round_trip_sync(self, tmp_path, monkeypatch):
        """REGRESSION: sync_index was called with web_updates in the positional
        slot for fulltext_updates.  A second sync_index (e.g. on a subsequent
        run) must preserve the web entry's URL that was set on the first run."""
        media_db_path = tmp_path / "media-db"
        monkeypatch.chdir(tmp_path)

        # First run — archive a web query
        with mock.patch.object(sys, "argv", [
            "media-db.py",
            "--source", "google-scholar",
            "--query", "endometriosis AND diet",
            "--search-slug", "roundtrip-test",
            "--topic", "endometriosis",
            "--media-db", str(media_db_path),
        ]):
            exit_code = media_db.main()
        assert exit_code == 0

        first_data = json.loads((media_db_path / "index.json").read_text())
        assert any("scholar.google.com" in w["url"] for w in first_data["web"])

        # Second run — archive another web query in the same topic to
        # trigger a second sync_index call (which exercises the round-trip
        # preservation path through load_existing_index_entries).
        with mock.patch.object(sys, "argv", [
            "media-db.py",
            "--source", "google-scholar",
            "--query", "endometriosis exercise",
            "--search-slug", "roundtrip-test-2",
            "--topic", "endometriosis",
            "--media-db", str(media_db_path),
        ]):
            exit_code = media_db.main()
        assert exit_code == 0

        second_data = json.loads((media_db_path / "index.json").read_text())
        # The first entry's URL must still be present after the round-trip
        assert any("scholar.google.com" in w["url"] for w in second_data["web"])
        # And both web files should be listed
        assert any("roundtrip-test" in w["path"] for w in second_data["web"])
        assert any("roundtrip-test-2" in w["path"] for w in second_data["web"])

    def test_no_arguments_prints_error(self, capsys):
        with mock.patch.object(sys, "argv", ["media-db.py"]):
            with pytest.raises(SystemExit):
                media_db.main()
        captured = capsys.readouterr()
        assert "provide --query" in captured.err.lower() or "error" in captured.err.lower()


class TestSyncIndexFlag:
    def test_sync_index_creates_index(self, tmp_path, monkeypatch):
        media_db_path = tmp_path / "media-db"
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(sys, "argv", [
            "media-db.py", "--sync-index", "--media-db", str(media_db_path),
        ]):
            exit_code = media_db.main()
        assert exit_code == 0
        assert (media_db_path / "index.json").is_file()
        data = json.loads((media_db_path / "index.json").read_text())
        assert "searches" in data
        assert "papers" in data

    def test_sync_index_creates_dirs(self, tmp_path, monkeypatch):
        media_db_path = tmp_path / "media-db"
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(sys, "argv", [
            "media-db.py", "--sync-index", "--media-db", str(media_db_path),
        ]):
            media_db.main()
        for name in ("searches", "papers", "fulltext", "guidelines", "web"):
            assert (media_db_path / name).is_dir()


class TestLabelFlag:
    def test_label_requires_path(self, capsys):
        with mock.patch.object(sys, "argv", ["media-db.py", "--label", "important"]):
            with pytest.raises(SystemExit):
                media_db.main()
        captured = capsys.readouterr()
        assert "path" in captured.err.lower() or "error" in captured.err.lower()

    def test_path_requires_label(self, capsys):
        with mock.patch.object(sys, "argv", ["media-db.py", "--path", "papers/x/y"]):
            with pytest.raises(SystemExit):
                media_db.main()
        captured = capsys.readouterr()
        assert "label" in captured.err.lower() or "error" in captured.err.lower()

    def test_set_label_on_entry(self, tmp_path, monkeypatch):
        media_db_path = tmp_path / "media-db"
        for name in ("searches", "papers", "fulltext", "guidelines", "web"):
            (media_db_path / name).mkdir(parents=True)
        # Create actual paper directory so sync_index preserves the entry
        paper_dir = media_db_path / "papers" / "test" / "pmid-1-title"
        paper_dir.mkdir(parents=True)
        meta = {"result": {"uids": ["1"]}}
        (paper_dir / "metadata.json").write_text(json.dumps(meta))
        (paper_dir / "abstract.txt").write_text("Test abstract.")
        # Pre-populate index.json with the entry
        index = {
            "searches": [],
            "papers": [{"path": "papers/test/pmid-1-title", "identifier": "PMID:1", "url": "http://x"}],
            "fulltext": [],
            "guidelines": [],
            "web": [],
        }
        (media_db_path / "index.json").write_text(json.dumps(index))
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(sys, "argv", [
            "media-db.py", "--label", "important",
            "--path", "papers/test/pmid-1-title",
            "--media-db", str(media_db_path),
        ]):
            exit_code = media_db.main()
        assert exit_code == 0
        data = json.loads((media_db_path / "index.json").read_text())
        assert data["papers"][0]["label"] == "important"

    def test_label_nonexistent_path(self, tmp_path, monkeypatch, capsys):
        media_db_path = tmp_path / "media-db"
        for name in ("searches", "papers", "fulltext", "guidelines", "web"):
            (media_db_path / name).mkdir(parents=True)
        index = {"searches": [], "papers": [], "fulltext": [], "guidelines": [], "web": []}
        (media_db_path / "index.json").write_text(json.dumps(index))
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(sys, "argv", [
            "media-db.py", "--label", "test",
            "--path", "papers/nonexistent/item",
            "--media-db", str(media_db_path),
        ]):
            exit_code = media_db.main()
        assert exit_code == 1


class TestFromLookupFlag:
    def test_from_lookup_bypasses_query_requirement(self, tmp_path, monkeypatch):
        media_db_path = tmp_path / "media-db"
        monkeypatch.chdir(tmp_path)
        fake_stdin = json.dumps({"results": []})
        with mock.patch.object(sys, "argv", [
            "media-db.py", "--from-lookup", "--topic", "test",
            "--media-db", str(media_db_path),
        ]), mock.patch.object(sys, "stdin", io.StringIO(fake_stdin)):
            exit_code = media_db.main()
        assert exit_code == 1  # fails because no results, but parse_args passes

    def test_from_lookup_no_results(self, tmp_path, monkeypatch):
        media_db_path = tmp_path / "media-db"
        monkeypatch.chdir(tmp_path)
        fake_stdin = json.dumps({"results": []})
        with mock.patch.object(sys, "argv", [
            "media-db.py", "--from-lookup", "--topic", "test",
            "--media-db", str(media_db_path),
        ]), mock.patch.object(sys, "stdin", io.StringIO(fake_stdin)):
            exit_code = media_db.main()
        assert exit_code == 1

    def test_from_lookup_invalid_json(self, tmp_path, monkeypatch):
        media_db_path = tmp_path / "media-db"
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(sys, "argv", [
            "media-db.py", "--from-lookup", "--topic", "test",
            "--media-db", str(media_db_path),
        ]), mock.patch.object(sys, "stdin", io.StringIO("not json")):
            exit_code = media_db.main()
        assert exit_code == 1
