"""Indeed et LinkedIn, via la bibliothèque JobSpy (https://github.com/Bunsly/JobSpy).

Contrairement aux autres fichiers de ce dossier, `fetch_jobspy` ne renvoie pas une liste
d'offres mais des tableaux pandas (un par appel) que la collecte assemble et met au format
standard : les deux sites passent par les mêmes réglages et la même gestion d'erreur.

On appelle JobSpy UN SITE À LA FOIS (et non `site_name=["indeed", "linkedin"]`) : si l'un
lève une exception (anti-bot, captcha…), l'autre continue."""

from __future__ import annotations

import math
import threading
from datetime import datetime, timezone

import pandas as pd
from jobspy import scrape_jobs
from jobspy.linkedin import LinkedIn

from veille import lecture_config as reglages
from veille.lecture_config import plafond
from veille.outils import titre_correspond

# Sites interrogés, activables dans config/sources.yml.
SITES = [s for s in ("indeed", "linkedin") if reglages.source_active(s)]

# Paramètres communs envoyés à JobSpy pour chaque appel.
COMMON_CONFIG = {
    "location": reglages.ZONE_PARIS,                      # zone de recherche (config/sources.yml)
    "country_indeed": "France",            # oriente Indeed sur le bon TLD (indeed.fr)
    "description_format": "markdown",      # plus propre à parser que du HTML brut
    "linkedin_fetch_description": True,    # LinkedIn renvoie une liste sans description : un appel de plus par offre
}

# Deuxième passage : offres 100 % télétravail, partout en France.
# Le passage principal est limité à « Paris, France » : il rate les postes en télétravail
# complet rattachés à un siège en région.
#   - Indeed : `is_remote=True` filtre sur « télétravail complet » (exclut l'hybride).
#   - LinkedIn : JobSpy ignore `is_remote` ; on ajoute nous-mêmes le paramètre de recherche
#     LinkedIn f_WT=2 (« À distance ») avec le correctif ci-dessous.
REMOTE_CONFIG = {
    "location": reglages.ZONE_TELETRAVAIL,
    "is_remote": True,
}

_original_linkedin_search_params = LinkedIn._search_params


def _linkedin_search_params_with_remote(self) -> dict:
    """Ajoute f_WT=2 (télétravail) aux paramètres LinkedIn quand is_remote=True."""
    params = _original_linkedin_search_params(self)
    if self.scraper_input.is_remote:
        params["f_WT"] = "2"
    return params


LinkedIn._search_params = _linkedin_search_params_with_remote

# LinkedIn : ne télécharger la description que des offres dont l'intitulé correspond à un mot-clé.
# JobSpy ouvre la page de CHAQUE offre de la liste pour en lire la description (une requête par
# offre) ; or la collecte écarte ensuite, d'après l'intitulé, la plupart d'entre elles. On saute donc
# cette requête pour les autres. Les offres sautées sont de toute façon écartées par le filtre de
# titre de collecte_quotidienne.py (même règle, mêmes mots-clés) : elles n'arrivent jamais à la notation.
_MOTS_CLES: list[str] = []          # renseigné par fetch_jobspy
_etat = threading.local()           # JobSpy lit les offres en parallèle : l'indicateur est propre à chaque fil

_original_process_job = LinkedIn._process_job
_original_fetch_details = LinkedIn._fetch_details


def _process_job_sans_detail_hors_titre(self, job_card, job_id):
    """Repère l'intitulé sur la carte de l'offre et mémorise s'il faut ouvrir la page de l'offre."""
    tag = job_card.find("h3", class_="base-search-card__title")
    titre = tag.get_text(strip=True) if tag is not None else ""
    _etat.sauter = bool(_MOTS_CLES) and not titre_correspond(titre, _MOTS_CLES)
    try:
        return _original_process_job(self, job_card, job_id)
    finally:
        _etat.sauter = False


def _fetch_details_si_titre_retenu(self, job_id):
    if getattr(_etat, "sauter", False):
        return {}
    return _original_fetch_details(self, job_id)


LinkedIn._process_job = _process_job_sans_detail_hors_titre
LinkedIn._fetch_details = _fetch_details_si_titre_retenu


def fetch_jobspy(ctx) -> list[pd.DataFrame]:
    """Scrape JobSpy site par site, mot-clé par mot-clé (Paris, puis télétravail en France).

    Les tableaux non vides sont accumulés ; une erreur est enregistrée au bilan
    sans interrompre le reste. `hours_old` est calculé site par site : temps écoulé
    depuis le dernier succès du site (marge de chevauchement comprise), arrondi au-dessus,
    minimum 1 h (0 désactiverait le filtre côté API)."""
    all_dfs: list[pd.DataFrame] = []
    _MOTS_CLES[:] = [e["term"] for e in ctx.searches]

    hours_old_by_site = {}
    for site in SITES:
        delta_hours = (datetime.now(timezone.utc) - ctx.since(site)).total_seconds() / 3600
        hours_old_by_site[site] = max(1, math.ceil(delta_hours))
        print(f"  JobSpy {site} : hours_old = {hours_old_by_site[site]}h (depuis son dernier succès, marge comprise)")

    resultats = {site: plafond(site, "resultats_par_recherche", 20) for site in SITES}

    for entry in ctx.searches:
        term = entry["term"]
        for site in SITES:
            for scope, extra in (("Paris", {}), ("télétravail", REMOTE_CONFIG)):
                recherche = "teletravail" if scope == "télétravail" else "paris"
                parametres = {
                    **COMMON_CONFIG,
                    "hours_old": hours_old_by_site[site],
                    **extra,
                    "results_wanted": resultats[site],   # plafond par site (config/sources.yml)
                    "site_name": [site],        # JobSpy attend une liste, même pour un seul site
                    "search_term": term,
                }
                label = f"{site} / {scope} / '{term}'"
                try:
                    df = scrape_jobs(**parametres)
                    ctx.ok(site, len(df))
                    if len(df) >= resultats[site]:
                        ctx.plafond(site, f"'{term}' ({scope}) : {len(df)} résultats")
                    if len(df) > 0:
                        df["recherche"] = recherche
                        print(f"  ✓ {label} → {len(df)} offres")
                        all_dfs.append(df)
                    else:
                        print(f"  · {label} → 0 offres")
                except Exception as e:
                    # Exception courte : les traces complètes brouillent les logs sans aider en CI.
                    print(f"  ✗ {label} → {type(e).__name__}: {str(e)[:80]}")
                    ctx.error(site, f"{type(e).__name__}: {str(e)[:150]}")
    return all_dfs
