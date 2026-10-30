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


if __name__ == "__main__":
    main(globals())
