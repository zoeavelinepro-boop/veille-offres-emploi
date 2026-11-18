"""Filtre de titre : ne garde que les offres dont l'intitulé contient un mot-clé de recherche, et consigne les autres.

Après la collecte, seules les offres dont le titre correspond à un terme de
`config/mots-recherches.yml` sont conservées (voir `outils.titre_correspond`). Les autres ne sont
pas perdues de vue : chacune est consignée ici, une seule fois, dans un fichier par mois
(`data/etat/offres_ecartees_AAAA-MM.csv`). Il sert à vérifier que le filtre n'écarte pas de
bonnes offres, et à décider d'ajouter un mot-clé si des offres intéressantes y reviennent."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from veille import lecture_config as reglages
from veille.outils import titre_correspond

COLONNES = ["date_collecte", "site", "titre", "recruteur", "lieu", "lien"]


def filtrer(offres: list[dict], termes: list[str]) -> tuple[list[dict], list[dict]]:
    """Sépare les offres en (gardées, écartées) : gardée = titre contenant tous les mots d'un terme."""
    gardees, ecartees = [], []
    for o in offres:
        (gardees if titre_correspond(o.get("title") or "", termes) else ecartees).append(o)
    return gardees, ecartees


def chemin(date: datetime) -> Path:
    return reglages.ETAT_DIR / f"offres_ecartees_{date:%Y-%m}.csv"


def _cle(lien: str, titre: str, recruteur: str) -> str:
    return lien or f"{titre}|{recruteur}"


def journaliser(ecartees: list[dict], date: datetime) -> int:
    """Ajoute au journal du mois les offres pas encore consignées ; renvoie le nombre ajouté."""
    fichier = chemin(date)
    deja: set[str] = set()
    if fichier.exists():
        with open(fichier, encoding="utf-8", newline="") as f:
            for ligne in csv.DictReader(f, delimiter=";"):
                deja.add(_cle(ligne["lien"], ligne["titre"], ligne["recruteur"]))
    nouvelles = []
    for o in ecartees:
        titre, recruteur = str(o.get("title") or ""), str(o.get("recruiter") or "")
        lien = str(o.get("job_url") or "")
        cle = _cle(lien, titre, recruteur)
        if cle in deja:
            continue
        deja.add(cle)
        nouvelles.append([f"{date:%Y-%m-%d}", o.get("site") or "", titre, recruteur,
                          str(o.get("location") or ""), lien])
    if nouvelles:
        fichier.parent.mkdir(parents=True, exist_ok=True)
        ecrire_entete = not fichier.exists()
        with open(fichier, "a", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=";")
            if ecrire_entete:
                w.writerow(COLONNES)
            w.writerows(nouvelles)
    return len(nouvelles)
