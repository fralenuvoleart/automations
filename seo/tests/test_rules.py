"""Tests for seo/rules.py — fixtures are real outputs of the "PBS - SEO Rankings" sheet (2026-10-30)."""
import contextlib
import copy
import io
import json
import sys
import tempfile
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "tests"))
import rules  # noqa: E402
from _runner import main  # noqa: E402

R = rules.load("pbservices.ge")
DATA = json.loads(rules.rules_path("pbservices.ge").read_text())


def row(**k):
    return {"clicks": 0.0, "impressions": 0.0, "ctr": 0.0, "position": 0.0, **k}


def test_rules_file_is_valid_and_portable():
    assert rules.validate(DATA, "pbservices.ge") == []
    bad = copy.deepcopy(DATA)
    bad["query_categories"]["rules"][0]["regex"] = "pb(?=services)"
    assert any("not portable" in i for i in rules.validate(bad))


def test_validate_catches_config_mistakes():
    bad = copy.deepcopy(DATA)
    bad["channels"]["ai_channel"] = "Bots"
    bad["keywords"]["auto"]["category_caps"]["Brand"] = 1
    bad["keywords"]["tracked"].append({"keyword": "внж по ип в грузии", "category": "Residency", "type": "Core"})
    bad["keywords"]["tracked"].append({"keyword": "pb georgia", "category": "IE", "type": "Brand"})
    issues = " | ".join(rules.validate(bad))
    assert "ai_channel" in issues and "category_caps.Brand" in issues
    assert "duplicate of 'внж грузии по ип'" in issues and "type Brand ⇔ category Brand" in issues


def test_duplicate_keys_match_the_sheet():
    sheet = {  # Keyword Setup → "Duplicate key" column
        "ип в грузии": "грузи ип", "внж грузии по ип": "внж грузи ип", "tax residency georgia": "georg resid tax",
        "статус малого бизнеса в грузии": "бизне грузи малог стату", "ооо в грузии": "грузи ооо",
        "pb services georgia": "georg pb servi", "pbservices": "pbser", "bank account": "accou bank",
        "it внж грузия": "it внж грузи", "格鲁吉亚银行开户": "格鲁吉亚银",
        "производственный календарь 2026 грузия": "2026 грузи кален произ",
        "как получить внж в грузии россиянину": "внж грузи как получ росси",
    }
    for q, key in sheet.items():
        assert R.keyword_key(q) == key, q
    assert R.keyword_key("внж по ип в грузии") == R.keyword_key("внж грузии по ип")


def test_query_categories_match_the_sheet():
    sheet = {
        "pb service": "Brand", "налог на недвижимость в грузии": "Tax", "налоговое резидентство грузии": "Tax",
        "it внж грузия": "Residency", "безвизовый режим": "Residency", "регистрация ип в грузии": "IE",
        "ипотека в грузии": "Real estate", "bank account": "Bank account", "solo bank": "Bank account",
        "格鲁吉亚银行开户": "Bank account", "gecrypto": "Crypto & PSP licensing",
        "aml комплаенс psp грузия": "Crypto & PSP licensing", "llc registration": "Company",
        "apostille": "Apostille", "регистрация брака в грузии": "Marriage", "юрист грузия": "Legal & Accounting",
        "annual accounts preparation georgia": "Legal & Accounting", "выходные в грузии 2026": "Generic",
        "районы тбилиси": "Generic", "gürcistan market fiyatları": "Generic", "коворкинг тбилиси": "Generic",
    }
    for q, cat in sheet.items():
        assert R.query_category(q) == cat, (q, R.query_category(q))
    assert R.rule_category("птд грузия") is None and R.query_category("птд грузия") == "Generic"  # unclassified
    assert R.query_category("юрист по недвижимости") == "Real estate"  # rule order matters
    assert R.is_brand("PB Services") and not R.is_brand("services georgia")


def test_pages_and_channels_match_the_sheet():
    pages = {  # GA4 Data → Page (full URL), Page tag, Language
        "/ru/blog/proizvodstvennyj-kalendar-gruzii": ("https://pbservices.ge/ru/blog/proizvodstvennyj-kalendar-gruzii/", "Blog", "RU"),
        "/services/individual-entrepreneur-georgia": ("https://pbservices.ge/services/individual-entrepreneur-georgia/", "Services", "EN"),
        "/ru": ("https://pbservices.ge/ru/", "Homepage", "RU"),
        "/": ("https://pbservices.ge/", "Homepage", "EN"),
        "/ru/uslugi/razreshenie-rabotu-gruzii": ("https://pbservices.ge/ru/uslugi/razreshenie-rabotu-gruzii/", "Services", "RU"),
        "/zh/about/keti-tskhomaria": ("https://pbservices.ge/zh/about/keti-tskhomaria/", "Other pages", "ZH"),
        "(not set)": ("(not set)", "Other pages", "EN"),
        "https://pbservices.ge/blog/how-to-open-a-bank-account-in-georgia/#step-by-step":
            ("https://pbservices.ge/blog/how-to-open-a-bank-account-in-georgia/", "Blog", "EN"),
    }
    for url, (clean, tag, lang) in pages.items():
        assert (R.clean(url), R.page_tag(url), R.page_language(url)) == (clean, tag, lang), url
    channels = {"google / organic": "Organic search", "yandex / cpc": "Paid search", "(direct) / (none)": "Direct",
                "cn.bing.com / referral": "Referral", "chatgpt.com / ai-assistant": "AI assistants",
                "perplexity / (not set)": "AI assistants", "newsletter / email": "Other"}
    for sm, ch in channels.items():
        assert R.channel(sm) == ch, sm


def test_derived_profile_values():
    assert R.languages() == ["EN", "RU", "AR", "ZH"]
    assert R.sections() == ["Services", "Blog", "Homepage", "Other pages"]
    assert R.services()[-1] == "Marriage" and "Generic" not in R.services()
    pk = R.priority_keywords()
    assert len(pk["ru"]) == 12 and len(pk["en"]) == 8 and pk["zh"] == [] and pk["ar"] == []
    assert "pb services" not in sum(pk.values(), [])  # brand keywords are tracked, not priority


def test_select_keywords_proven_opportunity_generic():
    pool = [
        row(query="налог на недвижимость в грузии", clicks=15, impressions=68, position=1.7),   # Proven (Tax)
        row(query="ипотека в грузии", clicks=7, impressions=31, position=4.0),                  # Proven (Real estate)
        row(query="ипотека в грузии для россиян", clicks=8, impressions=39, position=4.4),      # Proven (Real estate)
        row(query="квартира в тбилиси", clicks=6, impressions=40, position=3.0),                # cap 2 reached
        row(query="внж по ип в грузии", clicks=9, impressions=38, position=2.3),                # duplicate of Core
        row(query="solo bank", clicks=13, impressions=105, position=8.5),                       # excluded word
        row(query="налоговая грузии", clicks=1, impressions=15, position=5.4),                  # Opportunity
        row(query="llc registration", clicks=1, impressions=1027, position=5.9),                # Opportunity (top)
        row(query="apostille", clicks=0, impressions=37, position=9.3),                         # Opportunity
        row(query="apostille service", clicks=0, impressions=30, position=9.0),                 # Apostille cap 1
        row(query="vat georgia", clicks=0, impressions=50, position=25.0),                      # outside 5-20
        row(query="производственный календарь 2026 грузия", clicks=313, impressions=409, position=1.0),
        row(query="выходные в грузии 2026", clicks=153, impressions=769, position=2.3),
        row(query="праздники в грузии 2026", clicks=139, impressions=934, position=2.6),        # 3rd generic
        row(query="птд грузия", clicks=40, impressions=37, position=6.7),                       # unclassified
        row(query="pb services", clicks=242, impressions=919, position=1.6),                    # tracked Brand
    ]
    res = R.select_keywords(pool)
    by_type = {}
    for k in res["keywords"]:
        by_type.setdefault(k["type"], []).append(k["keyword"])
    assert len(by_type["Core"]) == 20 and by_type["Brand"] == ["pb services", "pb services georgia", "pbservices"]
    assert by_type["Proven"] == ["налог на недвижимость в грузии", "ипотека в грузии для россиян", "ипотека в грузии"]
    assert by_type["Opportunity"] == ["llc registration", "apostille", "налоговая грузии"]
    assert by_type["Generic"] == ["производственный календарь 2026 грузия", "выходные в грузии 2026"]
    brand = next(k for k in res["keywords"] if k["keyword"] == "pb services")
    assert brand["clicks"] == 242 and brand["target_page"] == "https://pbservices.ge/"
    assert [u["keyword"] for u in res["unclassified_to_review"]] == ["птд грузия"]
    assert res["truncated"] is False and res["lookback_days"] == 90


def test_select_keywords_status_vs_previous():
    cur = [row(query="налоговое резидентство грузии", clicks=1, impressions=3, position=1.0),        # New
           row(query="bank account georgia", impressions=2, position=7.0)]
    prev = [row(query="ип в грузии", clicks=1, impressions=3, position=7.3),                       # Lost
            row(query="bank account georgia", impressions=1, position=7.0)]
    ks = {k["keyword"]: k for k in R.select_keywords(cur, prev)["keywords"]}
    assert ks["налоговое резидентство грузии"]["status"] == "New"
    assert ks["ип в грузии"]["status"] == "Lost" and ks["внж грузии"]["status"] == "No impressions"
    assert ks["bank account georgia"]["status"] == "" and ks["bank account georgia"]["position_change"] == 0.0
    big = [row(query=f"q{i}", impressions=1, position=50) for i in range(25000)]  # truncated pull
    ks = {k["keyword"]: k for k in R.select_keywords(big + cur, prev)["keywords"]}
    assert ks["ип в грузии"]["status"] == "beyond row cutoff"


def test_breakdown_by_category_and_page_tag():
    cur = [row(query="pb services", page="https://pbservices.ge/", clicks=41, impressions=173, position=1.5),
           row(query="ипотека в грузии", page="https://pbservices.ge/ru/blog/x/", clicks=2, impressions=18, position=3.7)]
    prev = [row(query="pb services", page="https://pbservices.ge/", clicks=25, impressions=128, position=1.3),
            row(query="ипотека в грузии", page="https://pbservices.ge/ru/blog/x/#a", clicks=12, impressions=46, position=3.9)]
    out = R.breakdown(cur, "category", prev, min_impressions=50)
    rows_ = {r["category"]: r for r in out["rows"]}
    assert list(rows_) == ["Real estate", "Brand"]  # services order first, then Brand/Generic
    assert rows_["Brand"]["clicks_change_pct"] == 64.0 and rows_["Brand"]["position_change"] == -0.2
    assert rows_["Real estate"]["low_volume"] is True and rows_["Brand"]["low_volume"] is False
    assert out["total"]["clicks"] == 43 and "anonymized" in out["basis"]
    tags = {r["page_tag"]: r for r in R.breakdown(cur, "page_tag", prev)["rows"]}
    assert tags["Blog"]["prev"]["clicks"] == 12  # fragment URL counted on its page
    langs = {r["language"]: r["clicks"] for r in R.breakdown(cur, "language")["rows"]}
    assert langs == {"EN": 41, "RU": 2}


def test_jump_link_variants_merge_into_their_page():
    rows = [row(query="ип в грузии", page="https://pbservices.ge/ru/blog/registracziya-ip-v-gruzii/", clicks=13, impressions=1123, position=7.5),
            row(query="ип в грузии", page="https://pbservices.ge/ru/blog/registracziya-ip-v-gruzii/#section_1", clicks=1, impressions=1060, position=7.8),
            row(query="ип в грузии", page="https://pbservices.ge/ru/blog/registracziya-ip-v-gruzii/#section_4", impressions=1060, position=7.8)]
    out = R.collapse_fragments(rows)
    assert len(out) == 1 and out[0]["impressions"] == 1123 and out[0]["clicks"] == 14 and out[0]["position"] == 7.5


def test_targets_flag_wrong_page_and_not_ranking():
    blog = "https://pbservices.ge/blog/georgias-ten-best-banks/"
    rows = [  # 90-day Search Console rows for tracked keywords (2026-10-30)
        row(query="bank account georgia", page=blog, impressions=53, position=11.7),
        row(query="bank account georgia", page=blog + "#ranking", impressions=3, position=9.3),
        row(query="bank account georgia", page="https://pbservices.ge/services/bank-account-georgia/", clicks=1, impressions=26, position=22.3),
        row(query="внж грузии по ип", page="https://pbservices.ge/ru/blog/oformlenie-vnzh-gruzii-po-ip/", clicks=55, impressions=762, position=2.8),
        row(query="residence permit georgia", page="https://pbservices.ge/blog/georgian-residence-permit-for-it-specialists/", clicks=1, impressions=123, position=12.8),
        row(query="not tracked", page=blog, impressions=999, position=1)]
    res = {t["keyword"]: t for t in R.targets(rows)["targets"]}
    bank = res["bank account georgia"]
    assert bank["status"] == "wrong page" and bank["top_page"]["page"] == blog and bank["top_page"]["impressions"] == 53
    assert bank["target"]["position"] == 22.3 and bank["target"]["share"] == round(26 / 79, 3)
    assert res["внж грузии по ип"]["status"] == "ok" and "top_page" not in res["внж грузии по ип"]
    assert res["residence permit georgia"]["status"] == "target not ranking" and res["residence permit georgia"]["target"] is None
    assert res["статус малого бизнеса в грузии"]["status"] == "no impressions"
    assert list(res)[0] == "bank account georgia" or res[list(res)[0]]["status"] == "wrong page"  # wrong page first


def test_every_tracked_keyword_has_a_target_page():
    assert all(t.get("target_page", "").startswith("https://pbservices.ge/") for t in R.tracked.values())
    bad = copy.deepcopy(DATA)
    bad["keywords"]["tracked"][0]["target_page"] = "/ru/blog/x/"
    assert any("target_page must be an absolute" in i for i in rules.validate(bad))


def test_keywords_top_countries_like_the_sheet():
    q = [row(query="открыть ип в грузии", clicks=7, impressions=37, position=7.4)]
    geo = [row(country="rus", query="открыть ип в грузии", impressions=34), row(country="ltu", query="открыть ип в грузии", impressions=2),
           row(country="uzb", query="открыть ип в грузии", impressions=1), row(country="kaz", query="открыть ип в грузии", impressions=0)]
    ks = {k["keyword"]: k for k in R.select_keywords(q, country_rows=geo)["keywords"]}
    assert ks["открыть ип в грузии"]["countries_text"] == "RUS 92%, LTU 5%, UZB 3%"  # sheet: "RUS 92%, LTU 5%, UZB 3%"
    assert ks["внж грузии"]["countries_text"] == "No data"
    tiny = [row(country="geo", query="pb services", impressions=999), row(country="prt", query="pb services", impressions=1)]
    ks = {k["keyword"]: k for k in R.select_keywords([], country_rows=tiny)["keywords"]}
    assert ks["pb services"]["countries_text"] == "GEO 100%, PRT <1%"


def test_trend_by_week_for_categories_pages_and_keywords():
    w1 = [row(query="pb services", page="https://pbservices.ge/", clicks=35, impressions=111, position=1.3),
          row(query="ипотека в грузии", page="https://pbservices.ge/ru/blog/ipoteka/", clicks=6, impressions=44, position=4.4)]
    w2 = [row(query="pb services", page="https://pbservices.ge/", clicks=41, impressions=173, position=1.5),
          row(query="pb services", page="https://pbservices.ge/#about", clicks=1, impressions=170, position=1.5)]
    cat = R.trend([("2026-10-12", w1), ("2026-10-19", w2)], "category", min_impressions=50)
    rows_ = {r["category"]: r for r in cat["rows"]}
    assert cat["weeks"] == ["2026-10-12", "2026-10-19"]
    assert rows_["Brand"]["clicks"] == [35, 42] and rows_["Real estate"]["clicks"] == [6, 0]
    assert rows_["Real estate"]["position"] == [4.4, None] and rows_["Real estate"]["low_volume"] == [True, True]
    assert cat["total"]["clicks"] == [41, 42]
    tags = {r["page_tag"]: r for r in R.trend([("w1", w1), ("w2", w2)], "page_tag")["rows"]}
    assert tags["Homepage"]["impressions"] == [111, 173]  # #about merged into the homepage, not double-counted
    kw = R.trend([("w1", w1), ("w2", w2)], "keyword")
    names = {r["keyword"]: r for r in kw["rows"]}
    assert names["pb services"]["type"] == "Brand" and names["ипотека в грузии"]["type"] == "Proven"
    assert kw["total"]["keyword"] == "Tracked keywords" and kw["truncated_weeks"] == []


def test_cli_classify_validate_keywords():
    def run(*args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = rules.main(["--site", "pbservices.ge", *args])
        return code, buf.getvalue()
    code, out = run("validate")
    assert code == 0 and "OK" in out
    code, out = run("classify", "--query", "внж по ип в грузии")
    assert code == 0 and json.loads(out)["category"] == "Residency"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump({"rows": [{"keys": ["ипотека в грузии"], "clicks": 7, "impressions": 31, "ctr": 0.2, "position": 4}]},
                  fh, ensure_ascii=False)
    code, out = run("keywords", "--query", fh.name)
    assert code == 0 and any(k["type"] == "Proven" for k in json.loads(out)["keywords"])
    with contextlib.redirect_stderr(io.StringIO()):
        assert rules.main(["--site", "no-such-site.ge", "validate"]) == 1


def test_cli_trend_labels_weeks_from_recorded_calls_and_targets():
    import orchestrate
    import record
    with tempfile.TemporaryDirectory() as d:
        with contextlib.redirect_stdout(io.StringIO()):
            orchestrate.main(["--skill", "seo-rank-tracking", "--weeks", "2", "--as-of", "2026-10-30", "--out-dir", d])
        files = []
        for i, (s, e) in enumerate((("2026-10-12", "2026-10-18"), ("2026-10-19", "2026-10-25"))):
            raw = json.dumps({"rows": [{"keys": ["pb services"], "clicks": 10 + i, "impressions": 100, "ctr": 0.1, "position": 1.2}]})
            record.record(Path(d), f"query_w{i + 1}", raw, cap="gsc.query",
                          args={"siteUrl": "sc-domain:pbservices.ge", "startDate": s, "endDate": e})
            files.append(f"{d}/data/query_w{i + 1}.json")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert rules.main(["--site", "pbservices.ge", "trend", "--by", "category", "--rows", *files]) == 0
        out = json.loads(buf.getvalue())
        assert out["weeks"] == ["2026-10-12", "2026-10-19"] and out["total"]["clicks"] == [10, 11]
        raw = json.dumps({"rows": [{"keys": ["vasp georgia", "https://pbservices.ge/services/crypto-license-georgia/"],
                                    "clicks": 5, "impressions": 129, "ctr": 0.04, "position": 6.8}]})
        record.record(Path(d), "pq", raw, cap="gsc.page_query",
                      args={"siteUrl": "sc-domain:pbservices.ge", "startDate": "2026-10-12", "endDate": "2026-10-25"})
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert rules.main(["--site", "pbservices.ge", "targets", "--page-query", f"{d}/data/pq.json"]) == 0
        assert {t["keyword"]: t["status"] for t in json.loads(buf.getvalue())["targets"]}["vasp georgia"] == "ok"


if __name__ == "__main__":
    main(globals())
