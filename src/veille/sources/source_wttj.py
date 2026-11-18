"""Welcome to the Jungle (API Algolia publique du site).

Une fonction `fetch_*` par source ; voir veille/sources/__init__.py pour l'ordre d'appel."""

from __future__ import annotations

import json


from veille.lecture_config import plafond
from veille.sources._commun import (
    algolia_query,
    record,
    strip_html,
    ts_to_date,
)

RESULTATS_PAR_RECHERCHE = plafond("wttj", "resultats_par_recherche", 50)


# =============================================================================
# WELCOME TO THE JUNGLE
# =============================================================================
# API Algolia publique, celle qu'utilise le site lui-même (clé de recherche en
# lecture seule, liée au Referer du site).
WTTJ_APP_ID = "CSEKHVMS53"
WTTJ_API_KEY = "4bd8f6215d0cc52b26430765769e65a0"
WTTJ_INDEX = "wttj_jobs_production_fr"


def wttj_hit_to_record(hit: dict) -> dict | None:
    offices = hit.get("offices") or []
    in_fr = [o for o in offices if (o.get("country_code") or "").upper() == "FR"]
    idf = any((o.get("state") or "").lower().startswith("ile-de-france") or
              (o.get("local_state") or "").lower().startswith("île-de-france") for o in in_fr)
    full_remote = (hit.get("remote") or "") == "fulltime"
    # Périmètre : bureaux en Île-de-France, ou télétravail complet en France.
    if not (idf or (full_remote and (in_fr or not offices))):
        return None
    org = hit.get("organization") or {}
    office = (in_fr[0] if in_fr else (offices[0] if offices else {}))
    loc = ", ".join(p for p in [office.get("city"), office.get("state")] if p)
    parts = [hit.get("summary") or ""]
    missions = hit.get("key_missions") or []
    if missions:
        parts.append("Missions :\n" + "\n".join(f"- {m}" for m in missions))
    parts.append(strip_html(hit.get("profile")))
    if org.get("summary"):
        parts.append(f"À propos de {org.get('name', '')} : {org['summary']}")
    sal_min = hit.get("salary_yearly_minimum") or hit.get("salary_minimum") or ""
    sal_max = hit.get("salary_maximum") if hit.get("salary_period") == "yearly" else ""
    return record(
        title=hit.get("name", ""),
        recruiter=org.get("name", ""),
        location=loc,
        is_remote=full_remote,
        job_type=hit.get("contract_type", ""),
        min_amount=sal_min, max_amount=sal_max or "", currency=hit.get("salary_currency", "") if sal_min else "",
        date_posted=(hit.get("published_at") or "")[:10] or ts_to_date(hit.get("published_at_timestamp")),
        description="\n\n".join(p for p in parts if p),
        job_url=f"https://www.welcometothejungle.com/fr/companies/{org.get('slug', '')}/jobs/{hit.get('slug', '')}",
        site="welcome_to_the_jungle",
        recherche="paris" if idf else "teletravail",
    )


def fetch_wttj(ctx) -> list[dict]:
    source = "wttj"
    since_ts = int(ctx.since(source).timestamp())
    offers, seen = [], set()
    for term in ctx.terms_fr + ctx.terms_en:
        try:
            data = algolia_query(WTTJ_APP_ID, WTTJ_API_KEY, WTTJ_INDEX, {
                "query": term, "hitsPerPage": RESULTATS_PAR_RECHERCHE,
                "numericFilters": json.dumps([f"published_at_timestamp>={since_ts}"]),
            }, referer="https://www.welcometothejungle.com/")
        except Exception as e:
            print(f"    ⚠ WTTJ '{term}' : {e}")
            ctx.error(source, f"{type(e).__name__}: {str(e)[:150]}")
            continue
        hits = data.get("hits", [])
        ctx.ok(source, len(hits))
        if len(hits) >= RESULTATS_PAR_RECHERCHE:
            ctx.plafond(source, f"'{term}' : {len(hits)} résultats")
        kept = 0
        for hit in hits:
            if hit.get("objectID") in seen or int(hit.get("published_at_timestamp") or since_ts) < since_ts:
                continue
            seen.add(hit.get("objectID"))
            rec = wttj_hit_to_record(hit)
            if rec:
                offers.append(rec)
                kept += 1
        print(f"    WTTJ '{term}' → {len(hits)} offres, {kept} retenues (IDF ou 100 % télétravail)")
    return offers
