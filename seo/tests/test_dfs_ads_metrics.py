"""Tests for seo/dfs_metrics.py and seo/ads_metrics.py (third-party/Ads response analysis)."""
import sys
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "tests"))

import ads_metrics as A  # noqa: E402
import dfs_metrics as D  # noqa: E402
from _runner import main  # noqa: E402


def test_dfs_items_from_tasks_envelope():
    payload = {"tasks": [{"result": [{"items": [{"anchor": "x"}]}]}]}
    assert D.items(payload) == [{"anchor": "x"}]
    try:
        D.items({"weird": 1})
        raise AssertionError
    except ValueError:
        pass


def test_anchor_mix_buckets_and_risk():
    items = [{"anchor": "PB Services", "backlinks": 50}, {"anchor": "https://pbservices.ge", "backlinks": 20},
             {"anchor": "подробнее", "backlinks": 10}, {"anchor": "bank account georgia", "backlinks": 15},
             {"anchor": "", "backlinks": 5}]
    out = D.anchor_mix(items, ["pb services"], "pbservices.ge", ["bank account georgia"])
    s = out["shares"]
    assert s["brand"] == 0.5 and s["url"] == 0.2 and s["generic"] == 0.1 and s["exact_match"] == 0.15
    assert out["exact_match_risk"] is True and "heuristic" in out["label"]


def test_link_and_keyword_gap():
    gap = D.link_gap([{"domain": "a.com"}], [{"domain": "www.a.com", "rank": 9}, {"domain": "b.com", "rank": 50}])
    assert [g["domain"] for g in gap] == ["b.com"]
    ranked = [{"keyword_data": {"keyword": "ооо в грузии", "keyword_info": {"search_volume": 900}},
               "ranked_serp_element": {"serp_item": {"rank_group": 3, "url": "https://c.ge/x"}}},
              {"keyword_data": {"keyword": "have it", "keyword_info": {"search_volume": 50}}}]
    q = [{"query": "Have It", "clicks": 1, "impressions": 10, "ctr": 0.1, "position": 9}]
    out = D.keyword_gap(ranked, q)
    assert out == [{"keyword": "ооо в грузии", "search_volume": 900, "competitor_position": 3, "competitor_url": "https://c.ge/x"}]


def test_ads_rows_accept_result_wrapper():
    rows = A.ads_rows({"result": [{"search_term_view.search_term": "t", "metrics.cost_micros": 2_500_000}]})
    assert rows and rows[0]["term"] == "t" and rows[0]["cost"] == 2.5


def test_ads_overlap_buckets_and_money():
    ads = A.ads_rows([
        {"search_term_view": {"search_term": "pb services"}, "metrics": {"cost_micros": 5_000_000, "clicks": 50,
                                                                         "conversions": 2, "absolute_top_impression_percentage": 0.9}},
        {"search_term_view.search_term": "open bank account georgia", "metrics.cost_micros": "3000000",
         "metrics.clicks": "10", "metrics.conversions": "1", "metrics.absolute_top_impression_percentage": "0.3"},
        {"search_term_view": {"search_term": "llc georgia"}, "metrics": {"cost_micros": 2_000_000, "clicks": 5, "conversions": 1}},
    ])
    q = [{"query": "PB Services", "clicks": 200, "impressions": 300, "ctr": 0.6, "position": 1.1},
         {"query": "open bank account georgia", "clicks": 30, "impressions": 900, "ctr": 0.03, "position": 2.5},
         {"query": "tax residency georgia", "clicks": 40, "impressions": 800, "ctr": 0.05, "position": 4}]
    out = A.overlap(ads, q)
    assert {r["term"] for r in out["double_paying"]} == {"pb services", "open bank account georgia"}
    assert [r["term"] for r in out["defend_check"]] == ["open bank account georgia"]
    assert [r["term"] for r in out["paid_only_winners"]] == ["llc georgia"]
    assert [r["term"] for r in out["organic_only"]] == ["tax residency georgia"]
    assert out["summary"]["double_paying_spend"] == 8.0 and "estimate" in out["summary"]["label"]


if __name__ == "__main__":
    main(globals())
