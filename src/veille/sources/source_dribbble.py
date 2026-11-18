"""Dribbble Jobs : offres design et direction artistique, internationales (beaucoup en télétravail).

Flux RSS `/jobs.rss` (titres « <Employeur> is hiring for a position of <Intitulé> in
<Lieu> »), filtre de titre local et de lieu, puis JSON-LD de la page de l'offre pour
la description (vide dans le flux). Structure relevée le 08/11/2026."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

from veille.lecture_config import plafond
from veille.outils import intitule_exclu
from veille.sources._commun import get, titre_retenu
from veille.sources._mode import detail_ld, lieu_accepte, offre_depuis_ld

DB_FEED = "https://dribbble.com/jobs.rss"
DB_TITRE_RE = re.compile(r"^(?P<emp>.+?) is hiring for a position of (?P<titre>.+?)(?: in (?P<lieu>.+))?$")
DB_MAX_DETAILS = plafond("dribbble", "max_details", 30)


def fetch_dribbble(ctx) -> list[dict]:
    source = "dribbble"
    since = ctx.since(source)
    session = requests.Session()
    try:
        r = get(session, DB_FEED)
        r.raise_for_status()
        items = ET.fromstring(r.content).findall(".//item")
    except Exception as e:
        ctx.error(source, f"flux : {type(e).__name__}: {str(e)[:120]}")
        return []
    ctx.ok(source, len(items))
    cartes = []
    for it in items:
        m = DB_TITRE_RE.match((it.findtext("title") or "").strip())
        url = (it.findtext("link") or "").strip().split("?")[0]
        if not m or not url:
            continue
        try:
            date = parsedate_to_datetime(it.findtext("pubDate") or "")
        except (TypeError, ValueError):
            date = None
        if date and date < since:
            continue
        titre, lieu = m.group("titre").strip(), (m.group("lieu") or "").strip()
        if intitule_exclu(titre) or not titre_retenu(ctx, titre, source):
            continue
        if not lieu_accepte(lieu):
            continue
        cartes.append((url, titre, lieu, m.group("emp").strip(), date.strftime("%Y-%m-%d") if date else ""))
    offres = []
    for url, titre, lieu, emp, jour in cartes[:DB_MAX_DETAILS]:
        rec = offre_depuis_ld(detail_ld(session, url), url, titre, source, since, ctx.max_desc,
                              location=lieu, recruteur=emp, date_posted=jour)
        if rec:
            offres.append(rec)
    if len(cartes) > DB_MAX_DETAILS:
        ctx.plafond(source, f"{len(cartes)} offres, {DB_MAX_DETAILS} pages de détail lues")
    print(f"    Dribbble → {len(items)} offres lues, {len(offres)} retenues")
    return offres
