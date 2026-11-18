"""Michael Page : cabinet de recrutement (site français, toutes fonctions).

Une recherche par mot-clé : `/jobs/<terme en minuscules, mots séparés par des tirets>`,
liens `/job-detail/...`, filtre de titre local, puis JSON-LD de chaque offre (lu en
mode tolérant : le site y laisse des retours à la ligne bruts). Michael Page est un
intermédiaire : l'employeur réel est à chercher dans la description.
Structure relevée le 08/11/2026."""

from __future__ import annotations

import re
import unicodedata

import requests

from veille.lecture_config import plafond
from veille.outils import intitule_exclu
from veille.sources._commun import get, titre_retenu
from veille.sources._mode import detail_ld, liens, offre_depuis_ld

MP_BASE = "https://www.michaelpage.fr"
MP_LINK_RE = re.compile(r"^/job-detail/[^?#]+$")
MP_MAX_DETAILS = plafond("michaelpage", "max_details", 80)


def slug(terme: str) -> str:
    """« Directrice artistique » → « directrice-artistique »."""
    t = unicodedata.normalize("NFKD", terme).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def fetch_michaelpage(ctx) -> list[dict]:
    source = "michaelpage"
    since = ctx.since(source)
    session = requests.Session()
    cartes, vus, slugs, echecs = [], set(), [], 0
    for terme in list(ctx.terms_fr) + list(ctx.terms_en):
        s = slug(terme)
        if s and s not in slugs:
            slugs.append(s)
    for s in slugs:
        try:
            r = get(session, f"{MP_BASE}/jobs/{s}")
            if r.status_code == 404:          # aucune offre pour ce terme
                continue
            r.raise_for_status()
        except Exception as e:
            echecs += 1
            if echecs == 3:
                ctx.error(source, f"recherche '{s}' : {type(e).__name__}: {str(e)[:120]}")
            continue
        nouveaux = [(u, t) for u, t in liens(r.text, MP_LINK_RE, MP_BASE) if u not in vus]
        ctx.ok(source, len(nouveaux))
        for u, t in nouveaux:
            vus.add(u)
            if t and not intitule_exclu(t) and titre_retenu(ctx, t, source):
                cartes.append((u, t))
    offres = []
    for u, t in cartes[:MP_MAX_DETAILS]:
        ld = detail_ld(session, u)
        rec = offre_depuis_ld(ld, u, ld.get("title") or t, source, since, ctx.max_desc, recruteur="Michael Page")
        if rec:
            offres.append(rec)
    if len(cartes) > MP_MAX_DETAILS:
        ctx.plafond(source, f"{len(cartes)} offres, {MP_MAX_DETAILS} pages de détail lues")
    print(f"    Michael Page → {len(vus)} offres lues, {len(offres)} retenues")
    return offres
