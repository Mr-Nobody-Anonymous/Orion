import json

from orion.research import ResearchDiscovery, build_research_report


def test_public_paper_discovery_maps_openalex_metadata() -> None:
    payload = {"results": [{
        "display_name": "Market regimes",
        "doi": "https://doi.org/example",
        "publication_date": "2025-01-01",
        "cited_by_count": 3,
        "authorships": [{"author": {"display_name": "Ada"}}],
        "abstract_inverted_index": {"Markets": [0], "change": [1]},
        "primary_location": {"landing_page_url": "https://example.test/paper"},
    }]}
    discovery = ResearchDiscovery(fetcher=lambda _: json.dumps(payload).encode("utf-8"))
    sources = discovery.discover_papers("market regime")
    assert sources[0].title == "Market regimes"
    assert sources[0].abstract == "Markets change"
    assert build_research_report("market regime", sources).evidence_status == "INSUFFICIENT_EVIDENCE"
