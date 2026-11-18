"""Constantes et outils partagés par les sources (une source par fichier dans ce dossier)."""

from __future__ import annotations

import html as html_lib
import json
import re
import time
from datetime import datetime, timezone

import requests

from veille.outils import HEADERS, USER_AGENT, titre_correspond

PAUSE = 0.5                      # secondes entre deux requêtes vers un même site
TIMEOUT = 30

# Départements d'Île-de-France : sert à étiqueter « paris » une offre APECITA
# ou Hellowork située dans la région.
IDF_DEPTS = ("75", "77", "78", "91", "92", "93", "94", "95")
IDF_WORDS = ("paris", "ile-de-france", "île-de-france", "hauts-de-seine", "seine-saint-denis",
             "val-de-marne", "essonne", "yvelines", "val-d'oise", "seine-et-marne")

def titre_retenu(ctx, titre: str, source: str = "") -> bool:
    """Vrai si l'intitulé correspond à l'un des mots-clés de config/mots-recherches.yml.

    Sert aux sources qui n'ont pas de recherche par mot-clé : on garde seulement
    les offres dont le titre contient tous les mots d'au moins un terme (voir veille.outils)."""
    retenu = titre_correspond(titre, [e["term"] for e in ctx.searches])
    compter = getattr(ctx, "titre", None)
    if compter and source:
        compter(source, retenu)        # alimente le bilan : titres examinés / retenus
    return retenu


# =============================================================================
# OUTILS COMMUNS
# =============================================================================

def strip_html(text: str | None) -> str:
    """HTML → texte brut lisible (paragraphes et listes conservés)."""
    if not text:
        return ""
    txt = html_lib.unescape(str(text))
    txt = re.sub(r"<br\s*/?>", "\n", txt, flags=re.I)
    txt = re.sub(r"</(p|div|h\d|ul|ol)>", "\n\n", txt, flags=re.I)
    txt = re.sub(r"<li[^>]*>", "\n- ", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", "", txt)
    txt = re.sub(r"[ \t\xa0]+", " ", txt)
    txt = re.sub(r"\s*\n\s*", "\n", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


def ts_to_date(ts) -> str:
    """Horodatage Unix → AAAA-MM-JJ (vide si absent)."""
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return ""


def is_idf(location: str) -> bool:
    loc = (location or "").lower()
    if any(w in loc for w in IDF_WORDS):
        return True
    m = re.search(r"\b(\d{2})(?:\d{3})?\b", loc)
    return bool(m and m.group(1) in IDF_DEPTS)


def record(**kw) -> dict:
    """Offre au format standard (champs absents = vides)."""
    base = {"title": "", "recruiter": "", "location": "", "is_remote": False, "job_type": "",
            "min_amount": "", "max_amount": "", "currency": "", "date_posted": "",
            "description": "", "job_url": "", "site": "", "recherche": ""}
    base.update({k: v for k, v in kw.items() if v is not None})
    return base


def get(session: requests.Session, url: str, **kw) -> requests.Response:
    time.sleep(PAUSE)
    return session.get(url, headers=HEADERS, timeout=TIMEOUT, **kw)


def algolia_query(app_id: str, api_key: str, index: str, params: dict, referer: str | None = None) -> dict:
    """Une requête de recherche Algolia (API publique en lecture seule du site)."""
    headers = {"X-Algolia-Application-Id": app_id, "X-Algolia-API-Key": api_key,
               "Content-Type": "application/json", "User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
        headers["Origin"] = referer.rstrip("/")
    body = {"params": "&".join(f"{k}={requests.utils.quote(str(v), safe='')}" for k, v in params.items())}
    url = f"https://{app_id.lower()}-dsn.algolia.net/1/indexes/{index}/query"
    time.sleep(PAUSE)
    r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
    if r.status_code == 400 and "numericFilters" in params:
        # Attribut de date non filtrable sur cet index : on relance sans le
        # filtre, et chaque source filtre ensuite la date elle-même.
        params = {k: v for k, v in params.items() if k != "numericFilters"}
        body = {"params": "&".join(f"{k}={requests.utils.quote(str(v), safe='')}" for k, v in params.items())}
        time.sleep(PAUSE)
        r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def job_posting_ld(page_html: str) -> dict:
    """Premier bloc JSON-LD de type JobPosting d'une page (ou {})."""
    for m in re.finditer(r'<script[^>]*type="application/ld(?:\+|&#x2B;)json"[^>]*>(.*?)</script>',
                         page_html, re.S | re.I):
        raw = m.group(1).strip()
        data = None
        for texte in (raw, html_lib.unescape(raw)):
            try:
                # strict=False : certains sites (Michael Page) laissent des retours à la ligne bruts dans les textes
                data = json.loads(texte, strict=False)
                break
            except ValueError:
                continue
        if data is None:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for it in items:
            if isinstance(it, dict) and it.get("@type") == "JobPosting":
                return it
    return {}


# Codes pays ISO fréquents dans le JSON-LD (addressCountry) → nom lisible.
_PAYS = {"FR": "France", "FRA": "France", "GB": "United Kingdom", "UK": "United Kingdom",
         "GBR": "United Kingdom", "US": "United States", "USA": "United States"}


def ld_location(ld: dict) -> str:
    loc = ld.get("jobLocation")
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    addr = (loc or {}).get("address", {}) if isinstance(loc, dict) else {}
    if isinstance(addr, dict):
        pays = addr.get("addressCountry")
        if isinstance(pays, dict):
            pays = pays.get("name") or pays.get("@id") or ""
        pays = _PAYS.get(str(pays or "").strip().upper(), pays)
        parts = [addr.get("addressLocality"), addr.get("postalCode"), addr.get("addressRegion"), pays]
        vus = []
        for p in parts:
            if p and str(p) not in vus:
                vus.append(str(p))
        return ", ".join(vus)
    return ""


def ld_salary(ld: dict) -> tuple:
    sal = ld.get("baseSalary") or {}
    if not isinstance(sal, dict):
        return "", "", ""
    val = sal.get("value")
    cur = sal.get("currency", "")
    if isinstance(val, dict):
        return val.get("minValue", "") or "", val.get("maxValue", "") or "", cur
    return "", "", cur
