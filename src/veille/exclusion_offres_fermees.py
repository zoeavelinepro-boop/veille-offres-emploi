#!/usr/bin/env python3
"""
veille/exclusion_offres_fermees.py — Écarte les offres qui ne sont plus en ligne.

Usage :

  PYTHONPATH=src python -m veille.exclusion_offres_fermees --fichier data/offres/offres_2026-10-19.json
      Vérifie chaque offre du fichier et le réécrit sans les offres fermées.
      Lancé par le workflow après chaque recherche, avant la notation.

Règle de prudence : une offre n'est écartée que sur un signal clair de
fermeture (page introuvable, mention "offre expirée", redirection LinkedIn
"offre expirée", offre absente de l'API France Travail). Si le site bloque
la vérification (anti-robot, limite de requêtes) ou répond de façon
ambiguë, l'offre est conservée et comptée comme "inconnue".

Conçu pour tourner dans GitHub Actions (réseau ouvert).
"""

import argparse
import json
import os
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from veille import lecture_config as reglages
from veille.outils import HEADERS, MAX_DESC_CHARS
from veille.sources.source_france_travail import fetch_france_travail_token

OUTPUT_DIR = reglages.OFFRES_DIR
RUN_REPORT_FILE = reglages.BILAN_FILE

# Requêtes simultanées et pause entre deux requêtes, par site. LinkedIn et
# Indeed limitent vite le nombre de requêtes : on reste lent sur ces deux-là.
SITE_LIMITS = {
    "linkedin": (3, 0.5),
    "indeed": (3, 0.5),
    "france_travail": (4, 0.2),
}
DEFAULT_LIMIT = (2, 0.5)

# Budget de temps : au-delà, les offres restantes ne sont plus vérifiées et
# sont conservées ("inconnu"), pour que le workflow ne dépasse jamais sa limite.
BUDGET_SECONDS = float(os.environ.get("VERIF_BUDGET_MINUTES", "10")) * 60
STARTED_AT = time.monotonic()

# Mentions qui signalent une offre fermée (comparaison en minuscules).
CLOSED_MARKERS = {
    "linkedin": [
        "no longer accepting applications",
        "n’accepte plus de candidatures",
        "n'accepte plus de candidatures",
        "n’accepte plus les candidatures",
        "n'accepte plus les candidatures",
    ],
    "indeed": [
        "this job has expired",
        "cette offre d'emploi a expiré",
        "cette offre d’emploi a expiré",
        "cette offre a expiré",
        "n'est plus disponible",
        "n’est plus disponible",
    ],
}

FT_DETAIL_RE = re.compile(r"/offres/recherche/detail/([A-Za-z0-9]+)")

_ft_token: str | None = None
_ft_token_lock = threading.Lock()


def _ft_token_cached() -> str | None:
    global _ft_token
    with _ft_token_lock:
        if _ft_token is None:
            _ft_token = fetch_france_travail_token() or ""
        return _ft_token or None


def check_france_travail(offer: dict) -> str:
    """Interroge l'API France Travail sur l'identifiant de l'offre."""
    offer_id = offer.get("id_france_travail")
    if not offer_id:
        m = FT_DETAIL_RE.search(str(offer.get("job_url") or ""))
        offer_id = m.group(1) if m else None
    token = _ft_token_cached()
    if not offer_id or not token:
        return check_page(offer)  # pas d'identifiant : vérification de la page
    resp = requests.get(
        f"https://api.francetravail.io/partenaire/offresdemploi/v2/offres/{offer_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    if resp.status_code == 200:
        return "active"
    if resp.status_code in (204, 404, 410):
        return "fermee"
    return "inconnu"


def check_page(offer: dict) -> str:
    """Ouvre la page de l'offre et cherche un signal clair de fermeture."""
    site = offer.get("site") or ""
    url = str(offer.get("job_url") or "")
    if not url.startswith("http"):
        return "inconnu"
    resp = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    final_url = resp.url or url
    if resp.status_code in (404, 410):
        return "fermee"
    if resp.status_code != 200:
        return "inconnu"  # 403, 429, 999… : site qui bloque, on conserve
    if site == "linkedin" and ("expired_jd_redirect" in final_url or "/jobs/view/" not in final_url):
        return "fermee"
    text = resp.text.lower()
    if any(marker in text for marker in CLOSED_MARKERS.get(site, [])):
        return "fermee"
    # LinkedIn renvoie parfois l'offre sans description (environ 1 sur 10) :
    # on profite de la page déjà ouverte pour la compléter, sinon la notation
    # n'a que l'intitulé pour juger (secteur, employeur réel…).
    if site == "linkedin" and not str(offer.get("description") or "").strip():
        description = extract_linkedin_description(resp.text)
        if description:
            offer["description"] = description[:MAX_DESC_CHARS]
    return "active"


def extract_linkedin_description(html: str) -> str:
    """Texte de la description d'une page d'offre LinkedIn (version publique)."""
    soup = BeautifulSoup(html, "html.parser")
    node = (soup.select_one(".show-more-less-html__markup")
            or soup.select_one(".description__text")
            or soup.select_one("[class*=description]"))
    if not node:
        return ""
    for br in node.find_all("br"):
        br.replace_with("\n")
    for li in node.find_all("li"):
        li.insert_before("\n- ")
    text = node.get_text(" ", strip=False)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text.strip()


def check_offer(offer: dict) -> str:
    if time.monotonic() - STARTED_AT > BUDGET_SECONDS:
        return "inconnu"
    try:
        if offer.get("site") == "france_travail":
            return check_france_travail(offer)
        return check_page(offer)
    except Exception:
        return "inconnu"


def check_all(offers: list[dict]) -> list[str]:
    """Vérifie les offres site par site, avec un débit limité par site."""
    statuses: list[str | None] = [None] * len(offers)
    by_site: dict[str, list[int]] = {}
    for i, offer in enumerate(offers):
        by_site.setdefault(offer.get("site") or "?", []).append(i)

    def run_site(site: str, indexes: list[int]) -> None:
        workers, pause = SITE_LIMITS.get(site, DEFAULT_LIMIT)

        def one(i: int) -> None:
            statuses[i] = check_offer(offers[i])
            time.sleep(pause)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(one, indexes))
        c = Counter(statuses[i] for i in indexes)
        print(f"  {site} : {len(indexes)} offres → {c.get('active', 0)} actives, "
              f"{c.get('fermee', 0)} fermées, {c.get('inconnu', 0)} non vérifiables")

    # Les sites tournent en parallèle entre eux, chacun à son propre rythme.
    with ThreadPoolExecutor(max_workers=len(by_site) or 1) as pool:
        list(pool.map(lambda kv: run_site(*kv), by_site.items()))
    return [s or "inconnu" for s in statuses]


def filter_offers(offers: list[dict]) -> tuple[list[dict], dict]:
    statuses = check_all(offers)
    kept = [o for o, s in zip(offers, statuses) if s != "fermee"]
    summary = {
        "verifiees": len(offers),
        "actives": statuses.count("active"),
        "fermees_retirees": statuses.count("fermee"),
        "non_verifiables_conservees": statuses.count("inconnu"),
        "par_site": {},
    }
    for site in sorted({o.get("site") or "?" for o in offers}):
        sub = [s for o, s in zip(offers, statuses) if (o.get("site") or "?") == site]
        summary["par_site"][site] = dict(Counter(sub))
    return kept, summary


def write_json(path: Path, data) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def report(out_path: Path, kept: list[dict], summary: dict) -> None:
    """Ajoute le bilan au run_report et aux sorties GitHub Actions."""
    try:
        run_report = json.loads(RUN_REPORT_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        run_report = {}
    run_report["verification_en_ligne"] = {"fichier": str(out_path), **summary}
    run_report["offres_ecrites"] = len(kept) if run_report.get("fichier") == str(out_path) else run_report.get("offres_ecrites")
    write_json(RUN_REPORT_FILE, run_report)

    line = (f"Vérification en ligne : {summary['verifiees']} offres, "
            f"{summary['fermees_retirees']} fermées retirées, "
            f"{summary['non_verifiables_conservees']} non vérifiables conservées → "
            f"{len(kept)} offres dans {out_path}")
    print("\n" + line)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as f:
            f.write(f"\n{line}\n")
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as f:
            f.write(f"out_file={out_path}\ncount={len(kept)}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fichier", required=True, help="fichier d'offres à vérifier et réécrire")
    args = parser.parse_args()

    path = Path(args.fichier)
    offers = json.loads(path.read_text(encoding="utf-8"))
    print(f"Vérification de {len(offers)} offres de {path}…")
    kept, summary = filter_offers(offers)
    write_json(path, kept)
    report(path, kept, summary)


if __name__ == "__main__":
    main()
