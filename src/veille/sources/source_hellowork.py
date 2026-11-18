"""Hellowork (généraliste français).

Une fonction `fetch_*` par source ; voir veille/sources/__init__.py pour l'ordre d'appel."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from veille.outils import intitule_exclu
from veille.lecture_config import plafond
from veille.sources._commun import (
    get,
    job_posting_ld,
    ld_location,
    ld_salary,
    record,
    strip_html,
)


# =============================================================================
# HELLOWORK (généraliste français)
# =============================================================================
HW_BASE = "https://www.hellowork.com"
HW_SEARCH = HW_BASE + "/fr-fr/emploi/recherche.html?k={k}&l=Paris&st=date"
HW_MAX_DETAILS = plafond("hellowork", "max_details", 150)


def _hw_age_days(text: str) -> float | None:
    """« il y a 2 heures » → 0.08 ; « il y a 3 jours » → 3 ; inconnu → None."""
    m = re.search(r"il y a\s+(\d+)\s*\+?\s*(minute|heure|jour|semaine|mois)", text, re.I)
    if not m:
        return 0.0 if re.search(r"aujourd|à l'instant|nouveau", text, re.I) else None
    n, unit = int(m.group(1)), m.group(2).lower()
    return {"minute": n / 1440, "heure": n / 24, "jour": n, "semaine": 7 * n, "mois": 30 * n}[unit]


def fetch_hellowork(ctx) -> list[dict]:
    source = "hellowork"
    max_age = (datetime.now(timezone.utc) - ctx.since(source)).total_seconds() / 86400
    session = requests.Session()
    cards, seen = [], set()
    for term in ctx.terms_fr:
        try:
            r = get(session, HW_SEARCH.format(k=requests.utils.quote(term)))
            r.raise_for_status()
        except Exception as e:
            print(f"    ⚠ Hellowork '{term}' : {e}")
            ctx.error(source, f"{type(e).__name__}: {str(e)[:150]}")
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("li[data-id-storage-item-id]")
        ctx.ok(source, len(items))
        kept = 0
        for li in items:
            oid = li.get("data-id-storage-item-id")
            if not oid or oid in seen:
                continue
            seen.add(oid)
            title = (li.select_one('input[name="title"]') or {}).get("value", "")
            company = (li.select_one('input[name="company"]') or {}).get("value", "")
            text = li.get_text(" | ", strip=True)
            age = _hw_age_days(text)
            if age is not None and age > max_age:
                continue
            if intitule_exclu(title):
                continue
            cards.append({"id": oid, "title": title, "recruiter": company, "text": text})
            kept += 1
        print(f"    Hellowork '{term}' → {len(items)} offres, {kept} récentes")
    offers = []
    for c in cards[:HW_MAX_DETAILS]:
        url = f"{HW_BASE}/fr-fr/emplois/{c['id']}.html"
        try:
            d = get(session, url)
            ld = job_posting_ld(d.text) if d.status_code == 200 else {}
        except Exception as e:
            ctx.error(source, f"détail : {e}")
            ld = {}
        mn, mx, cur = ld_salary(ld)
        location = ld_location(ld)
        if not location:
            m = re.search(r"\|\s*([^|]+ - \d{2,3})\s*\|", c["text"])
            location = m.group(1).strip() if m else ""
        full_remote = bool(re.search(r"télétravail complet|full remote|100 ?% télétravail", c["text"], re.I))
        org = ld.get("hiringOrganization") or {}
        offers.append(record(
            title=c["title"] or ld.get("title", ""),
            recruiter=c["recruiter"] or ((org.get("name") if isinstance(org, dict) else "") or ""),
            location=location,
            is_remote=full_remote,
            job_type=ld.get("employmentType", "") if isinstance(ld.get("employmentType"), str) else "",
            min_amount=mn, max_amount=mx, currency=cur,
            date_posted=(ld.get("datePosted") or "")[:10],
            description=strip_html(ld.get("description")),
            job_url=url,
            site="hellowork",
            recherche="paris",
        ))
    if len(cards) > HW_MAX_DETAILS:
        ctx.plafond(source, f"{len(cards)} offres, {HW_MAX_DETAILS} pages de détail lues")
        print(f"    Hellowork : {len(cards) - HW_MAX_DETAILS} offres au-delà du plafond de {HW_MAX_DETAILS} détails, ignorées")
    print(f"    Hellowork → {len(offers)} offres")
    return offers
