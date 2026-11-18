"""Creative Boom : offres des métiers créatifs, surtout Royaume-Uni.

Liste `/jobs/` puis `/jobs/page-N/` (liens `/jobs/<intitulé>/`). Le lien englobe toute
la carte (intitulé, employeur, lieu, salaire) : le filtre de titre porte sur l'adresse
de l'offre, puis le JSON-LD de chaque offre donne le reste. Structure relevée le 08/11/2026."""

from __future__ import annotations

import re

import requests

from veille.lecture_config import plafond
from veille.sources._mode import collecte_liste

CB_BASE = "https://www.creativeboom.com"
CB_LINK_RE = re.compile(r"^/jobs/(?!page-\d+/?$)[a-z0-9-]+/?$")
CB_MAX_PAGES = plafond("creativeboom", "max_pages", 4)
CB_MAX_DETAILS = plafond("creativeboom", "max_details", 40)


def fetch_creativeboom(ctx) -> list[dict]:
    pages = [f"{CB_BASE}/jobs/" + ("" if n == 1 else f"page-{n}/") for n in range(1, CB_MAX_PAGES + 1)]
    return collecte_liste(ctx, "creativeboom", requests.Session(), pages, CB_LINK_RE, CB_BASE,
                          CB_MAX_DETAILS, titre_slug=True)
