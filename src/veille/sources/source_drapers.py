"""Drapers Jobs : mode et distribution, Royaume-Uni surtout.

Liste générale `/jobs?page=N` (liens `/job/<identifiant>/<intitulé>/`), filtre de
titre local, puis JSON-LD de chaque offre. Les postes à Londres sont écartés par la
zone (Paris, France, Europe ou télétravail). Structure relevée le 08/11/2026."""

from __future__ import annotations

import re

import requests

from veille.lecture_config import plafond
from veille.sources._mode import collecte_liste

DR_BASE = "https://www.drapersjobs.com"
DR_LINK_RE = re.compile(r"^/job/[^/]+(/[^/]+)?/?$")
DR_MAX_PAGES = plafond("drapers", "max_pages", 5)
DR_MAX_DETAILS = plafond("drapers", "max_details", 60)


def fetch_drapers(ctx) -> list[dict]:
    pages = [f"{DR_BASE}/jobs" + ("" if n == 1 else f"?page={n}") for n in range(1, DR_MAX_PAGES + 1)]
    return collecte_liste(ctx, "drapers", requests.Session(), pages, DR_LINK_RE, DR_BASE, DR_MAX_DETAILS)
