"""Real keyword volumes via the Google Ads API (Keyword Planner).

Free with a Google Ads account (no spend). Non-spending accounts get volume
ranges (buckets) rather than exact numbers - still the only legit volume data.

Usage: .venv/bin/python ads_volumes.py "best running shoes" "running shoes near me" [--geo 1023652]
Config: .google-ads.yaml (0600). Default geo: US (2840); pass --geo with a
Google geo-target ID for metro-level volumes (e.g. 1023652 = Orlando, FL).
"""
import os
import sys

os.environ.setdefault("REQUESTS_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt")
HERE = os.path.dirname(os.path.abspath(__file__))

US_GEO = "2840"  # United States (neutral default; override with --geo)


def ideas(client, customer_id, seeds, geo=US_GEO):
    svc = client.get_service("KeywordPlanIdeaService")
    req = client.get_type("GenerateKeywordIdeasRequest")
    req.customer_id = customer_id
    req.language = "languageConstants/1000"  # English
    req.geo_target_constants.append(f"geoTargetConstants/{geo}")
    req.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
    for s in seeds:
        req.keyword_seed.keywords.append(s)
    req.keyword_annotation.extend([
        client.enums.KeywordPlanKeywordAnnotationEnum.KEYWORD_CONCEPT,
    ])
    resp = svc.generate_keyword_ideas(request=req)
    out = []
    for r in resp:
        m = r.keyword_idea_metrics
        vol = None
        if m.avg_monthly_searches:
            # v33: avg_monthly_searches is int64; buckets come as ranges on non-spenders
            vol = m.avg_monthly_searches
        out.append({
            "keyword": r.text,
            "volume": vol,
            "competition": client.enums.KeywordPlanCompetitionLevelEnum.Name(m.competition),
        })
    return sorted(out, key=lambda d: -(d["volume"] or 0))


def main():
    from google.ads.googleads.client import GoogleAdsClient
    args = [a for a in sys.argv[1:] if not a.startswith("--geo")]
    geo = US_GEO
    for a in sys.argv[1:]:
        if a.startswith("--geo="):
            geo = a.split("=", 1)[1]
        elif a == "--geo":
            ap_error = "--geo needs a value: --geo=<geo-target-id>"
            print(ap_error, file=sys.stderr)
            raise SystemExit(2)
    seeds = args or ["best running shoes"]
    client = GoogleAdsClient.load_from_storage(os.path.join(HERE, ".google-ads.yaml"))
    customer_id = "7121367015"  # FF + GC manager account
    rows = ideas(client, customer_id, seeds, geo=geo)
    print(f"# {len(rows)} keyword ideas for {seeds}\n")
    for r in rows[:40]:
        print(f"- {r['keyword'][:60]:60} | vol {r['volume'] or '?':>8} | {r['competition']}")


if __name__ == "__main__":
    main()
