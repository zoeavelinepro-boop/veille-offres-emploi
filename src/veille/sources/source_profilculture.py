"""ProfilCulture : métiers de la culture, de l'art, du design et de la communication.

La recherche par mot-clé passe par un formulaire : on lit donc les catégories
utiles (pages `-page2`, `-page3`…, offres les plus récentes d'abord). Carte :
<h6> intitulé, <small> employeur puis lieu, date jj/mm/aa. Pas de JSON-LD : la
description est le texte de `div.left_col`. Structure relevée le 06/11/2026."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from veille.lecture_config import plafond
from veille.outils import intitule_exclu
from veille.sources._commun import get, is_idf, record, titre_retenu
from veille.sources._mode import lieu_accepte

PC_BASE = "https://www.profilculture.com"
PC_CATEGORIES = ["Emplois-Art-Design-Architecture", "Emplois-Edition-Presse-Communication"]
PC_LINK_RE = re.compile(r"^/annonce/[a-z0-9-]+-(\d{5,})\.html$")
PC_MAX_PAGES = plafond("profilculture", "max_pages", 5)
PC_MAX_DETAILS = plafond("profilculture", "max_details", 60)


def fetch_profilculture(ctx) -> list[dict]:
    source = "profilculture"
    since = ctx.since(source) - timedelta(days=1)
    session = requests.Session()
    cards, seen = [], set()
    for cat in PC_CATEGORIES:
        for page in range(1, PC_MAX_PAGES + 1):
            url = f"{PC_BASE}/annonce/{cat}" + (f"-page{page}" if page > 1 else "")
            try:
                r = get(session, url)
                r.raise_for_status()
            except Exception as e:
                ctx.error(source, f"{cat} page {page} : {type(e).__name__}: {str(e)[:120]}")
                break
            soup = BeautifulSoup(r.text, "html.parser")
            links = [a for a in soup.select("a[href]")
                     if PC_LINK_RE.match(a["href"].replace(PC_BASE, "").split("?")[0])]
            ctx.ok(source, len(links))
            old = 0
            for a in links:
                path = a["href"].replace(PC_BASE, "").split("?")[0]
                oid = PC_LINK_RE.match(path).group(1)
                if oid in seen:
                    continue
                seen.add(oid)
                h = a.find("h6")
                title = h.get_text(" ", strip=True) if h else a.get_text(" ", strip=True)
                smalls = [s.get_text(" ", strip=True) for s in a.find_all("small")]
                m = re.search(r"\b(\d{2})/(\d{2})/(\d{2})\b", a.get_text(" ", strip=True))
                posted = f"20{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""
                if posted and datetime.fromisoformat(posted).replace(tzinfo=timezone.utc) < since:
                    old += 1
                    continue
                if intitule_exclu(title) or not titre_retenu(ctx, title, source):
                    continue
                location = smalls[1] if len(smalls) > 1 else ""
                if not lieu_accepte(location):
                    continue
                cards.append({"url": PC_BASE + path, "title": title,
                              "recruiter": smalls[0] if smalls else "", "location": location, "posted": posted})
            if not links or old == len(links):   # fin de liste ou page entièrement ancienne
                break
    offers = []
    for c in cards[:PC_MAX_DETAILS]:
        description = ""
        try:
            d = get(session, c["url"])
            col = BeautifulSoup(d.text, "html.parser").select_one("div.left_col") if d.status_code == 200 else None
            description = col.get_text("\n", strip=True) if col else ""
        except Exception as e:
            ctx.error(source, f"détail : {e}")
        offers.append(record(
            title=c["title"], recruiter=c["recruiter"], location=c["location"],
            is_remote=bool(re.search(r"t[ée]l[ée]travail|remote", c["location"], re.I)),
            date_posted=c["posted"], description=description[:ctx.max_desc], job_url=c["url"],
            site=source, recherche="paris" if is_idf(c["location"]) else "teletravail",
        ))
    if len(cards) > PC_MAX_DETAILS:
        ctx.plafond(source, f"{len(cards)} offres, {PC_MAX_DETAILS} pages de détail lues")
    print(f"    ProfilCulture → {len(seen)} offres lues, {len(offers)} retenues")
    return offers
