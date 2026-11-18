"""FashionUnited : mode, liste des offres à Paris.

La recherche par mot-clé ne filtre pas sans JavaScript : on lit la liste des
offres à Paris (pages `?page=N`), on garde les intitulés qui correspondent aux
mots-clés, puis on lit le JSON-LD de chaque offre. Structure relevée le 05/11/2026."""

from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

from veille.lecture_config import plafond
from veille.outils import intitule_exclu
from veille.sources._commun import get, titre_retenu
from veille.sources._mode import detail_ld, offre_depuis_ld

FU_BASE = "https://fashionunited.fr"
FU_LIST = FU_BASE + "/fashion-jobs/search/a/Paris%2C%20%C3%8Ele-de-France"
FU_LINK_RE = re.compile(r"^/fashion-jobs/[a-z0-9-]+-(\d{6,})$")
FU_MAX_PAGES = plafond("fashionunited", "max_pages", 5)
FU_MAX_DETAILS = plafond("fashionunited", "max_details", 60)


def fetch_fashionunited(ctx) -> list[dict]:
    source = "fashionunited"
    since = ctx.since(source)
    session = requests.Session()
    cards, seen = [], set()
    for page in range(1, FU_MAX_PAGES + 1):
        url = FU_LIST if page == 1 else f"{FU_LIST}?page={page}"
        try:
            r = get(session, url)
            r.raise_for_status()
        except Exception as e:
            ctx.error(source, f"liste page {page} : {type(e).__name__}: {str(e)[:120]}")
            break
        soup = BeautifulSoup(r.text, "html.parser")
        new = 0
        for a in soup.select("a[href]"):
            path = a["href"].replace(FU_BASE, "").split("?")[0]
            m = FU_LINK_RE.match(path)
            if not m or m.group(1) in seen:
                continue
            seen.add(m.group(1))
            new += 1
            title = a.get_text(" ", strip=True)
            if title and not intitule_exclu(title) and titre_retenu(ctx, title, source):
                cards.append((FU_BASE + path, title))
        ctx.ok(source, new)
        if not new:                           # pagination absente ou fin de liste
            break
    offers = []
    for url, title in cards[:FU_MAX_DETAILS]:
        rec = offre_depuis_ld(detail_ld(session, url), url, title, source, since, ctx.max_desc)
        if rec:
            offers.append(rec)
    if len(cards) > FU_MAX_DETAILS:
        ctx.plafond(source, f"{len(cards)} offres, {FU_MAX_DETAILS} pages de détail lues")
    print(f"    FashionUnited → {len(seen)} offres lues, {len(offers)} retenues")
    return offers
