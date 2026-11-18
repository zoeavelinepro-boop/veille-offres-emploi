"""Fashion Personnel : cabinet de recrutement mode (Londres), postes au Royaume-Uni et en Europe.

Liste `/jobs?page=N` (liens `/job/<intitulé>-<numéro>`), filtre de titre local, puis
JSON-LD de chaque offre ; le lieu, absent du JSON-LD, est lu dans le titre de la page.
Fashion Personnel est un intermédiaire : l'employeur réel est à chercher dans la
description. Structure relevée le 08/11/2026."""

from __future__ import annotations

import re

import requests

from veille.lecture_config import plafond
from veille.sources._mode import collecte_liste

FP_BASE = "https://www.fashionpersonnel.co.uk"
FP_LINK_RE = re.compile(r"^/job/[a-z0-9-]+-\d+/?$")
FP_MAX_PAGES = plafond("fashionpersonnel", "max_pages", 5)
FP_MAX_DETAILS = plafond("fashionpersonnel", "max_details", 60)


def fetch_fashionpersonnel(ctx) -> list[dict]:
    pages = [f"{FP_BASE}/jobs" + ("" if n == 1 else f"?page={n}") for n in range(1, FP_MAX_PAGES + 1)]
    return collecte_liste(ctx, "fashionpersonnel", requests.Session(), pages, FP_LINK_RE, FP_BASE,
                          FP_MAX_DETAILS, lieu_titre_page=True, recruteur_defaut="Fashion Personnel")
