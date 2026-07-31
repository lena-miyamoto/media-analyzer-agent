"""Tests for media-db-lookup.py — external lookup without network calls."""

import json
import sys

import pytest

import media_db_lookup as ml


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

PUBMED_ESUMMARY = json.dumps({
    "result": {
        "uids": ["25946513"],
        "25946513": {
            "title": "Lisdexamfetamine increases cortical acetylcholine efflux",
            "source": "J Neurochem",
            "pubdate": "2015 Jul",
            "authors": [{"name": "Hutson PH"}, {"name": "Heal DJ"}],
            "articleids": [
                {"idtype": "pubmed", "value": "25946513"},
                {"idtype": "doi", "value": "10.1111/jnc.13157"},
            ],
        },
    }
})

PUBMED_EFETCH = (
    "1.  J Neurochem. 2015 Jul.\n\n"
    "Abstract\n\n"
    "Background: Lisdexamfetamine dimesylate (LDX) is a prodrug stimulant.\n"
    "Methods: In vivo microdialysis was performed in freely moving rats.\n"
    "Results: LDX significantly increased cortical acetylcholine efflux.\n"
    "Conclusions: These findings suggest cholinergic mechanisms contribute to LDX effects.\n\n"
    "Copyright 2015.\n"
)

PUBMED_ESEARCH_DOI = json.dumps({
    "esearchresult": {
        "idlist": ["25946513"],
        "querytranslation": "10.1111/jnc.13157[doi]",
        "count": "1",
    }
})

EUROPE_PMC_SEARCH = json.dumps({
    "resultList": {
        "result": [{
            "source": "MED",
            "id": "25946513",
            "pmid": "25946513",
            "doi": "10.1111/jnc.13157",
            "title": "Lisdexamfetamine increases cortical acetylcholine efflux",
            "authorString": "Hutson PH, Heal DJ",
            "journalTitle": "J Neurochem",
            "firstPublicationDate": "2015-07-01",
            "abstractText": "<h4>Background</h4><p>Lisdexamfetamine dimesylate (LDX) is a prodrug.</p><h4>Results</h4><p>LDX increased cortical ACh.</p>",
        }],
    },
})


# ---------------------------------------------------------------------------
# _extract_abstract_medline
# ---------------------------------------------------------------------------

class TestExtractAbstractMedline:
    def test_plain_text_single_newline_after_heading(self):
        raw = "1. Citation\n\nAbstract\nThis abstract uses one newline after the heading.\n"
        assert ml._extract_abstract_medline(raw) == "This abstract uses one newline after the heading."

    def test_plain_text_cuts_known_sections(self):
        raw = "Abstract\n\nMain abstract.\n\nMeSH terms\nTerm A\n"
        assert ml._extract_abstract_medline(raw) == "Main abstract."


# ---------------------------------------------------------------------------
# lookup_pmids
# ---------------------------------------------------------------------------

class TestLookupPmids:
    def test_single_pmid(self):
        def fake_fetch(endpoint, params):
            if "esummary" in endpoint:
                return PUBMED_ESUMMARY
            if "efetch" in endpoint:
                return PUBMED_EFETCH
            raise AssertionError(f"unexpected endpoint: {endpoint}")

        results = ml.lookup_pmids(["25946513"], fetch_func=fake_fetch)
        assert len(results) == 1
        r = results[0]
        assert r["source"] == "pubmed"
        assert r["pmid"] == "25946513"
        assert r["doi"] == "10.1111/jnc.13157"
        assert "cortical acetylcholine" in r["title"].lower()
        assert "Lisdexamfetamine" in r["abstract"]
        assert r["authors"] == ["Hutson PH", "Heal DJ"]
        assert r["journal"] == "J Neurochem"

    def test_batch_pmids(self):
        batch_summary = json.dumps({
            "result": {
                "uids": ["11111", "22222"],
                "11111": {
                    "title": "Paper One", "source": "J One", "pubdate": "2024",
                    "authors": [{"name": "A B"}],
                    "articleids": [{"idtype": "pubmed", "value": "11111"}],
                },
                "22222": {
                    "title": "Paper Two", "source": "J Two", "pubdate": "2024",
                    "authors": [{"name": "C D"}],
                    "articleids": [{"idtype": "pubmed", "value": "22222"}],
                },
            }
        })
        calls = []

        def fake_fetch(endpoint, params):
            calls.append((endpoint, params))
            if "esummary" in endpoint:
                return batch_summary
            if "efetch" in endpoint:
                return f"Abstract for {params['id']}"
            raise AssertionError(f"unexpected: {endpoint}")

        results = ml.lookup_pmids(["11111", "22222"], fetch_func=fake_fetch)
        assert len(results) == 2
        assert results[0]["pmid"] == "11111"
        assert results[1]["pmid"] == "22222"
        # esummary was called once with comma-separated IDs
        esummary_calls = [c for c in calls if "esummary" in c[0]]
        assert len(esummary_calls) == 1
        assert "11111" in esummary_calls[0][1]["id"]
        assert "22222" in esummary_calls[0][1]["id"]

    def test_missing_pmid(self):
        summary = json.dumps({
            "result": {
                "uids": ["99999"],
            }
        })

        def fake_fetch(endpoint, params):
            if "esummary" in endpoint:
                return summary
            raise AssertionError("should not reach efetch for missing PMID")

        results = ml.lookup_pmids(["99999"], fetch_func=fake_fetch)
        assert len(results) == 1
        assert "error" in results[0]

    def test_empty_list(self):
        results = ml.lookup_pmids([], fetch_func=lambda e, p: "{}")
        assert results == []

    def test_email_passed_to_pubmed(self):
        calls = []

        def fake_fetch(endpoint, params):
            calls.append((endpoint, params))
            if "esummary" in endpoint:
                return PUBMED_ESUMMARY
            if "efetch" in endpoint:
                return PUBMED_EFETCH
            raise AssertionError

        ml.lookup_pmids(["25946513"], email="test@example.com", fetch_func=fake_fetch)
        # esummary call
        esummary_params = calls[0][1]
        assert esummary_params["email"] == "test@example.com"
        # efetch call — REGRESSION: email was MISSING from per-PMID efetch calls
        efetch_params = calls[1][1]
        assert efetch_params["email"] == "test@example.com"

    def test_email_not_passed_when_none(self):
        """When email is None, neither esummary nor efetch should include it."""
        calls = []

        def fake_fetch(endpoint, params):
            calls.append(params)
            if "esummary" in endpoint:
                return PUBMED_ESUMMARY
            if "efetch" in endpoint:
                return PUBMED_EFETCH
            raise AssertionError

        ml.lookup_pmids(["25946513"], email=None, fetch_func=fake_fetch)
        for params in calls:
            assert "email" not in params

    def test_delay_between_pmids(self, monkeypatch):
        """REGRESSION: lookup_pmids had no delay between per-PMID efetch calls."""
        sleep_calls = []
        monkeypatch.setattr("time.sleep", sleep_calls.append)

        batch_summary = json.dumps({
            "result": {
                "uids": ["11111", "22222", "33333"],
                "11111": {
                    "title": "P1", "source": "J", "pubdate": "2024",
                    "authors": [], "articleids": [],
                },
                "22222": {
                    "title": "P2", "source": "J", "pubdate": "2024",
                    "authors": [], "articleids": [],
                },
                "33333": {
                    "title": "P3", "source": "J", "pubdate": "2024",
                    "authors": [], "articleids": [],
                },
            }
        })

        def fake_fetch(endpoint, params):
            if "esummary" in endpoint:
                return batch_summary
            if "efetch" in endpoint:
                return "Abstract text."
            raise AssertionError

        ml.lookup_pmids(["11111", "22222", "33333"], fetch_func=fake_fetch, delay=0.34)
        # With 3 PMIDs and delay > 0, sleep should be called 2 times
        # (between 1→2 and 2→3, but NOT after the last one)
        assert len(sleep_calls) == 2
        assert sleep_calls[0] == 0.34
        assert sleep_calls[1] == 0.34

    def test_no_delay_when_delay_is_zero(self, monkeypatch):
        """When delay=0, no sleep calls should be made."""
        sleep_calls = []
        monkeypatch.setattr("time.sleep", sleep_calls.append)

        def fake_fetch(endpoint, params):
            if "esummary" in endpoint:
                return PUBMED_ESUMMARY
            if "efetch" in endpoint:
                return PUBMED_EFETCH
            raise AssertionError

        ml.lookup_pmids(["25946513", "11111"], fetch_func=fake_fetch, delay=0)
        assert len(sleep_calls) == 0

    def test_no_delay_for_single_pmid(self, monkeypatch):
        """With a single PMID there's nothing to delay between."""
        sleep_calls = []
        monkeypatch.setattr("time.sleep", sleep_calls.append)

        def fake_fetch(endpoint, params):
            if "esummary" in endpoint:
                return PUBMED_ESUMMARY
            if "efetch" in endpoint:
                return PUBMED_EFETCH
            raise AssertionError

        ml.lookup_pmids(["25946513"], fetch_func=fake_fetch, delay=0.5)
        assert len(sleep_calls) == 0


# ---------------------------------------------------------------------------
# lookup_epmc_records
# ---------------------------------------------------------------------------

class TestLookupEpmcRecords:
    def test_single_record(self):
        def fake_fetch(module, params):
            return EUROPE_PMC_SEARCH

        results = ml.lookup_epmc_records(["MED:25946513"], fetch_func=fake_fetch)
        assert len(results) == 1
        r = results[0]
        assert r["source"] == "europe-pmc"
        assert r["pmid"] == "25946513"
        assert r["doi"] == "10.1111/jnc.13157"
        assert "cortical" in r["abstract"].lower()
        assert "<h4>" not in r["abstract"]  # HTML stripped

    def test_record_not_found(self):
        empty = json.dumps({"resultList": {"result": []}})

        def fake_fetch(module, params):
            return empty

        results = ml.lookup_epmc_records(["MED:99999"], fetch_func=fake_fetch)
        assert len(results) == 1
        assert "error" in results[0]

    def test_invalid_spec(self):
        results = ml.lookup_epmc_records(["invalid"], fetch_func=lambda m, p: "{}")
        assert len(results) == 1
        assert "invalid format" in results[0]["error"].lower()

    def test_api_error(self):
        def fake_fetch(module, params):
            raise RuntimeError("connection refused")

        results = ml.lookup_epmc_records(["MED:12345"], fetch_func=fake_fetch)
        assert len(results) == 1
        assert "connection refused" in results[0]["error"]

    def test_delay_between_records(self, monkeypatch):
        """lookup_epmc_records should sleep between records when delay > 0."""
        sleep_calls = []
        monkeypatch.setattr("time.sleep", sleep_calls.append)

        epmc_response = json.dumps({
            "resultList": {
                "result": [{
                    "source": "MED", "id": "11111", "pmid": "11111",
                    "doi": "10.1/foo", "title": "Test P1",
                    "authorString": "Smith J", "journalTitle": "J Test",
                    "firstPublicationDate": "2024-01-01",
                    "abstractText": "<p>Abstract 1</p>",
                }],
            },
        })

        def fake_fetch(module, params):
            return epmc_response

        ml.lookup_epmc_records(
            ["MED:11111", "MED:22222", "MED:33333"],
            fetch_func=fake_fetch,
            delay=0.34,
        )
        # 3 records → 2 sleep calls (between 1→2 and 2→3)
        assert len(sleep_calls) == 2
        assert sleep_calls[0] == 0.34
        assert sleep_calls[1] == 0.34

    def test_no_delay_when_delay_is_zero(self, monkeypatch):
        """When delay=0, no sleep calls should be made."""
        sleep_calls = []
        monkeypatch.setattr("time.sleep", sleep_calls.append)

        epmc_response = json.dumps({
            "resultList": {
                "result": [{
                    "source": "MED", "id": "11111", "pmid": "11111",
                    "doi": "10.1/foo", "title": "Test P1",
                    "authorString": "Smith J", "journalTitle": "J Test",
                    "firstPublicationDate": "2024-01-01",
                    "abstractText": "<p>Abstract 1</p>",
                }],
            },
        })

        def fake_fetch(module, params):
            return epmc_response

        ml.lookup_epmc_records(
            ["MED:11111", "MED:22222"],
            fetch_func=fake_fetch,
            delay=0,
        )
        assert len(sleep_calls) == 0

    def test_no_delay_for_single_record(self, monkeypatch):
        """With a single record there's nothing to delay between."""
        sleep_calls = []
        monkeypatch.setattr("time.sleep", sleep_calls.append)

        epmc_response = json.dumps({
            "resultList": {
                "result": [{
                    "source": "MED", "id": "11111", "pmid": "11111",
                    "doi": "10.1/foo", "title": "Test P1",
                    "authorString": "Smith J", "journalTitle": "J Test",
                    "firstPublicationDate": "2024-01-01",
                    "abstractText": "<p>Abstract 1</p>",
                }],
            },
        })

        def fake_fetch(module, params):
            return epmc_response

        ml.lookup_epmc_records(["MED:11111"], fetch_func=fake_fetch, delay=0.5)
        assert len(sleep_calls) == 0


# ---------------------------------------------------------------------------
# resolve_doi
# ---------------------------------------------------------------------------

class TestResolveDoi:
    def test_found_in_pubmed(self):
        def fake_fetch(endpoint, params):
            if "esearch" in endpoint:
                return PUBMED_ESEARCH_DOI
            if "esummary" in endpoint:
                return PUBMED_ESUMMARY
            if "efetch" in endpoint:
                return PUBMED_EFETCH
            raise AssertionError(f"unexpected: {endpoint}")

        result = ml.resolve_doi("10.1111/jnc.13157", pubmed_fetch_func=fake_fetch)
        assert result is not None
        assert result["pmid"] == "25946513"
        assert result["doi"] == "10.1111/jnc.13157"

    def test_found_in_europe_pmc_fallback(self):
        """When PubMed esearch returns no results, fall back to Europe PMC."""
        empty_pubmed = json.dumps({"esearchresult": {"idlist": [], "count": "0"}})

        def fake_fetch(endpoint_or_module, params):
            if isinstance(params, dict) and params.get("term", "").endswith("[doi]"):
                return empty_pubmed
            # Europe PMC search — return a DOI search result
            return json.dumps({
                "resultList": {
                    "result": [{
                        "source": "MED",
                        "id": "25946513",
                        "pmid": "25946513",
                        "doi": "10.1111/jnc.13157",
                        "title": "Test Title",
                        "authorString": "Hutson PH, Heal DJ",
                        "journalTitle": "J Neurochem",
                        "firstPublicationDate": "2015-07-01",
                        "abstractText": "<p>Abstract text</p>",
                    }],
                },
            })

        result = ml.resolve_doi("10.1111/jnc.13157", pubmed_fetch_func=fake_fetch, epmc_fetch_func=fake_fetch)
        assert result is not None
        assert result["source"] == "europe-pmc"
        assert result["pmid"] == "25946513"
        assert result["doi"] == "10.1111/jnc.13157"

    def test_not_found(self):
        empty_esearch = json.dumps({"esearchresult": {"idlist": [], "count": "0"}})
        empty_epmc = json.dumps({"resultList": {"result": []}})

        def fake_fetch(arg, params):
            if isinstance(params, dict) and params.get("term", "").endswith("[doi]"):
                return empty_esearch
            return empty_epmc

        result = ml.resolve_doi("10.9999/nonexistent", pubmed_fetch_func=fake_fetch, epmc_fetch_func=fake_fetch)
        assert result is None

    def test_europe_pmc_fallback_empty_record_id(self):
        """When EPMC returns a hit with no id and no pmid, return None gracefully."""
        empty_pubmed = json.dumps({"esearchresult": {"idlist": [], "count": "0"}})

        def fake_fetch(arg, params):
            if isinstance(params, dict) and params.get("term", "").endswith("[doi]"):
                return empty_pubmed
            # EPMC record missing both 'id' and 'pmid' keys
            return json.dumps({
                "resultList": {
                    "result": [{
                        "source": None,
                        "title": "Mystery paper with no identifier",
                        "doi": "10.9999/ghost",
                    }],
                },
            })

        result = ml.resolve_doi("10.9999/ghost", pubmed_fetch_func=fake_fetch, epmc_fetch_func=fake_fetch)
        assert result is None


# ---------------------------------------------------------------------------
# output formatting
# ---------------------------------------------------------------------------

class TestFormatOutput:
    def test_json_output(self):
        results = [{
            "source": "pubmed", "pmid": "123", "doi": "10.x", "title": "T",
            "abstract": "A", "authors": ["X"], "journal": "J", "publication_date": "2024", "url": "https://...",
        }]
        out = ml._format_json(results)
        data = json.loads(out)
        assert len(data["results"]) == 1
        assert data["results"][0]["pmid"] == "123"

    def test_text_output(self):
        results = [{
            "source": "pubmed", "pmid": "123", "doi": "10.x", "title": "Test Title",
            "abstract": "Test abstract.", "authors": ["Smith J"], "journal": "J Test",
            "publication_date": "2024 Mar", "url": "https://pubmed.ncbi.nlm.nih.gov/123/",
        }]
        out = ml._format_text(results)
        assert "PMID:    123" in out
        assert "Title:   Test Title" in out
        assert "Test abstract." in out

    def test_text_with_errors(self):
        results = [{"source": "pubmed", "pmid": "999", "error": "not found"}]
        out = ml._format_text(results)
        assert "ERROR:" in out


# ---------------------------------------------------------------------------
# CLI / main
# ---------------------------------------------------------------------------

class TestMain:
    def test_requires_id(self, capsys):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", ["media-db-lookup"])
            with pytest.raises(SystemExit):
                ml.main()

    def test_pmid_lookup(self, capsys):
        def fake_fetch(endpoint, params):
            if "esummary" in endpoint:
                return PUBMED_ESUMMARY
            if "efetch" in endpoint:
                return PUBMED_EFETCH
            raise AssertionError

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", ["media-db-lookup", "--pmid", "25946513"])
            mp.setattr(ml, "fetch_pubmed", fake_fetch)
            try:
                ml.main()
            except SystemExit:
                pass

        out = json.loads(capsys.readouterr().out)
        assert len(out["results"]) == 1
        assert out["results"][0]["pmid"] == "25946513"

    def test_epmc_record_lookup(self, capsys):
        def fake_fetch(module, params):
            return EUROPE_PMC_SEARCH

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", ["media-db-lookup", "--epmc-record", "MED:25946513"])
            mp.setattr(ml, "fetch_europe_pmc", fake_fetch)
            try:
                ml.main()
            except SystemExit:
                pass

        out = json.loads(capsys.readouterr().out)
        assert len(out["results"]) == 1
        assert out["results"][0]["source"] == "europe-pmc"
        assert out["results"][0]["pmid"] == "25946513"

    def test_text_format_flag(self, capsys):
        def fake_fetch(endpoint, params):
            if "esummary" in endpoint:
                return PUBMED_ESUMMARY
            if "efetch" in endpoint:
                return PUBMED_EFETCH
            raise AssertionError

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", ["media-db-lookup", "--pmid", "25946513", "--format", "text"])
            mp.setattr(ml, "fetch_pubmed", fake_fetch)
            try:
                ml.main()
            except SystemExit:
                pass

        out = capsys.readouterr().out
        assert "Result 1" in out
        assert "PMID:" in out


# ---------------------------------------------------------------------------
# utility: _strip_html
# ---------------------------------------------------------------------------

class TestStripHtml:
    def test_removes_tags(self):
        assert ml._strip_html("<p>Hello</p>") == "Hello"

    def test_decodes_entities(self):
        assert ml._strip_html("&amp;") == "&"
        assert ml._strip_html("&lt;") == "<"
        assert ml._strip_html("&gt;") == ">"

    def test_collapses_whitespace(self):
        assert ml._strip_html("<p>a  b</p>") == "a b"

    def test_empty_string(self):
        assert ml._strip_html("") == ""
        assert ml._strip_html(None) == ""
