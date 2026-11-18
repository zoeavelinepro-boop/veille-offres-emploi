"""If You Could Jobs : offres créatives (design, direction artistique), surtout Royaume-Uni.

La page d'accueil liste les offres récentes (liens `/jobs/<numéro>`) ; filtre de titre
local, puis JSON-LD de chaque offre. Structure relevée le 08/11/2026."""

from __future__ import annotations

import re

import requests

from veille.lecture_config import plafond
from veille.sources._mode import collecte_liste

IYC_BASE = "https://www.ifyoucouldjobs.com"
IYC_LINK_RE = re.compile(r"^/jobs/\d+[^/]*/?$")
IYC_MAX_DETAILS = plafond("ifyoucould", "max_details", 40)


def fetch_ifyoucould(ctx) -> list[dict]:
    return collecte_liste(ctx, "ifyoucould", requests.Session(), [IYC_BASE + "/"], IYC_LINK_RE, IYC_BASE,
                          IYC_MAX_DETAILS)
