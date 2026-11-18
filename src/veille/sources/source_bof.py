"""BoF Careers (Business of Fashion, plateforme Madgex) : mode et beauté, international.

Flux RSS de la recherche `/careers/jobsrss/?Keywords=<terme>` pour chaque mot-clé
anglais, puis JSON-LD de chaque offre (lieu, employeur, description).
Structure relevée le 05/11/2026."""

from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET

import requests

from veille.lecture_config import plafond
from veille.outils import intitule_exclu
from veille.sources._commun import get, titre_retenu
from veille.sources._mode import detail_ld, offre_depuis_ld

BOF_RSS = "https://www.businessoffashion.com/careers/jobsrss/?Keywords={k}"
BOF_MAX_DETAILS = plafond("bof", "max_details", 120)


def fetch_bof(ctx) -> list[dict]:
    source = "bof"
    since = ctx.since(source)
    session = requests.Session()
    cards, seen = [], set()
    for term in ctx.terms_en:                 # site anglophone : termes anglais seulement
        try:
            r = get(session, BOF_RSS.format(k=urllib.parse.quote_plus(term)))
            r.raise_for_status()
            items = ET.fromstring(r.content).findall(".//item")
        except Exception as e:
            ctx.error(source, f"flux '{term}' : {type(e).__name__}: {str(e)[:120]}")
            continue
        ctx.ok(source, len(items))
        for it in items:
            url = (it.findtext("link") or "").strip().split("?")[0]
            title = (it.findtext("title") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            if intitule_exclu(title) or not titre_retenu(ctx, title, source):
                continue
            cards.append((url, title))
    offers = []
    for url, title in cards[:BOF_MAX_DETAILS]:
        ld = detail_ld(session, url)
        rec = offre_depuis_ld(ld, url, ld.get("title") or title, source, since, ctx.max_desc)
        if rec:
            offers.append(rec)
    if len(cards) > BOF_MAX_DETAILS:
        ctx.plafond(source, f"{len(cards)} offres, {BOF_MAX_DETAILS} pages de détail lues")
    print(f"    BoF → {len(seen)} offres lues, {len(offers)} retenues")
    return offers
