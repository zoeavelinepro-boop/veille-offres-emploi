"""FashionJobs (offres affichées sur FashionNetwork) : mode, luxe, beauté.

Recherche plein texte `/s/?keyword=<terme>` pour chaque mot-clé ; liens
`/emploi/<recruteur>/<intitulé>,<id>.html` ; détail lu dans le JSON-LD de l'offre.
Structure relevée le 05/11/2026."""

from __future__ import annotations

import re
import urllib.parse

import requests
from bs4 import BeautifulSoup

from veille.lecture_config import plafond
from veille.outils import intitule_exclu
from veille.sources._commun import get, titre_retenu
from veille.sources._mode import detail_ld, offre_depuis_ld

FJ_BASE = "https://fr.fashionjobs.com"
FJ_SEARCH = FJ_BASE + "/s/?keyword={k}"
FJ_LINK_RE = re.compile(r"^/emploi/[^/]+/[^/]+,(\d+)\.html$")
FJ_MAX_DETAILS = plafond("fashionjobs", "max_details", 120)


def fetch_fashionjobs(ctx) -> list[dict]:
    source = "fashionjobs"
    since = ctx.since(source)
    session = requests.Session()
    cards, seen = [], set()
    for term in ctx.terms_fr + ctx.terms_en:
        try:
            r = get(session, FJ_SEARCH.format(k=urllib.parse.quote_plus(term)))
            r.raise_for_status()
        except Exception as e:
            ctx.error(source, f"recherche '{term}' : {type(e).__name__}: {str(e)[:120]}")
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        links = [a for a in soup.select("a[href]") if FJ_LINK_RE.match(a["href"].replace(FJ_BASE, ""))]
        ctx.ok(source, len(links))
        for a in links:
            path = a["href"].replace(FJ_BASE, "")
            oid = FJ_LINK_RE.match(path).group(1)
            title = a.get_text(" ", strip=True)
            if oid in seen or not title:
                continue
            seen.add(oid)
            if intitule_exclu(title) or not titre_retenu(ctx, title, source):
                continue
            cards.append((FJ_BASE + path, title))
    offers = []
    for url, title in cards[:FJ_MAX_DETAILS]:
        rec = offre_depuis_ld(detail_ld(session, url), url, title, source, since, ctx.max_desc)
        if rec:
            offers.append(rec)
    if len(cards) > FJ_MAX_DETAILS:
        ctx.plafond(source, f"{len(cards)} offres, {FJ_MAX_DETAILS} pages de détail lues")
    print(f"    FashionJobs → {len(seen)} liens, {len(offers)} offres retenues")
    return offers
