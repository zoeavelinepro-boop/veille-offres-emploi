"""SportyJob : emplois du sport et du sportswear (France surtout).

Flux RSS des offres `/?feed=job_feed&paged=N` (la recherche par mot-clé du site ne
filtre pas), lu page par page jusqu'aux offres plus anciennes que le dernier passage ;
filtre de titre local. Lieu, employeur et description viennent du flux.
Structure relevée le 08/11/2026."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

from veille.lecture_config import plafond
from veille.outils import intitule_exclu
from veille.sources._commun import get, titre_retenu
from veille.sources._mode import offre_depuis_ld

SJ_FEED = "https://sportyjob.com/?feed=job_feed&paged={n}"
SJ_MAX_PAGES = plafond("sportyjob", "max_pages", 10)


def _champ(item, nom: str) -> str:
    """Texte du premier sous-élément nommé `nom`, quel que soit son espace de noms."""
    for el in item:
        if el.tag.split("}")[-1] == nom:
            return (el.text or "").strip()
    return ""


def fetch_sportyjob(ctx) -> list[dict]:
    source = "sportyjob"
    since = ctx.since(source)
    session = requests.Session()
    offres, vus = [], set()
    for n in range(1, SJ_MAX_PAGES + 1):
        try:
            r = get(session, SJ_FEED.format(n=n))
            if n > 1 and r.status_code == 404:     # fin du flux
                break
            r.raise_for_status()
            items = ET.fromstring(r.content).findall(".//item")
        except Exception as e:
            if n == 1:
                ctx.error(source, f"flux : {type(e).__name__}: {str(e)[:120]}")
            break
        ctx.ok(source, len(items))
        if not items:
            break
        recentes = 0
        for it in items:
            url = (_champ(it, "link") or "").split("?")[0]
            titre = _champ(it, "title")
            try:
                date = parsedate_to_datetime(_champ(it, "pubDate"))
            except (TypeError, ValueError):
                date = None
            if date and date < since:
                continue
            recentes += 1
            if not url or url in vus:
                continue
            vus.add(url)
            if intitule_exclu(titre) or not titre_retenu(ctx, titre, source):
                continue
            rec = offre_depuis_ld({}, url, titre, source, since, ctx.max_desc,
                                  location=_champ(it, "location"), recruteur=_champ(it, "company"),
                                  description=_champ(it, "encoded") or _champ(it, "description"),
                                  date_posted=date.strftime("%Y-%m-%d") if date else "")
            if rec:
                offres.append(rec)
        if not recentes:                           # page entière plus ancienne que le dernier passage
            break
    else:
        ctx.plafond(source, f"{SJ_MAX_PAGES} pages de flux lues, offres plus anciennes non lues")
    print(f"    SportyJob → {len(vus)} offres récentes, {len(offres)} retenues")
    return offres
