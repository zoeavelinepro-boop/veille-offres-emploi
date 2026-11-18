"""Configuration de la veille : réglages lus dans `config/` et chemins des données.

Les réglages (mots-clés, exclusions, sources actives, seuils d'alerte) sont dans
les fichiers YAML du dossier `config/` à la racine du dépôt : les modifier ne
demande aucune connaissance de Python. Ce module les lit une seule fois.

Les chemins des données (`data/`) sont relatifs au dossier de travail : le
programme se lance depuis la racine du dépôt (comme le fait le workflow GitHub).
Variable d'environnement facultative : VEILLE_CONFIG = dossier de configuration
à utiliser à la place de `config/` (tests, essais).
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

RACINE_DEPOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = Path(os.environ.get("VEILLE_CONFIG") or RACINE_DEPOT / "config")

# --- Chemins des données (relatifs au dossier de travail) ---------------------
DATA_DIR = Path("data")
OFFRES_DIR = DATA_DIR / "offres"                       # offres collectées : offres_AAAA-MM-JJ[_HHMM].json
ETAT_DIR = DATA_DIR / "etat"                           # état de la collecte
BILAN_FILE = ETAT_DIR / "bilan_dernier_passage.json"   # bilan du dernier run, par source
DERNIER_SUCCES_FILE = ETAT_DIR / "dernier_succes_par_source.json"
NOTATION_DIR = DATA_DIR / "notation"                   # tenu par la notation (tâche Claude)
FICHIERS_NOTES_FILE = NOTATION_DIR / "fichiers_notes.json"
JOURNAUX_DIR = NOTATION_DIR / "journaux"               # journal_AAAA-MM.csv
REFERENCES_DIR = NOTATION_DIR / "references"           # offres déjà présentes dans Notion avant la veille
OFFRES_NOTION_CONNUES_FILE = REFERENCES_DIR / "offres_notion_connues.csv"
OFFRES_PREFIXE = "offres_"                             # début du nom des fichiers d'offres


def _lire(nom: str) -> dict:
    chemin = CONFIG_DIR / nom
    try:
        with open(chemin, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        raise SystemExit(f"Configuration illisible : {chemin} ({e})")
    if not isinstance(data, dict):
        raise SystemExit(f"Configuration vide ou mal formée : {chemin}")
    return data


_SOURCES = _lire("sources.yml")
_RECHERCHES = _lire("mots-recherches.yml")
_EXCLUSIONS = _lire("mots-exclus.yml")

# --- Recherches : [{"term": ..., "ft": True si terme français}, ...] -----------
RECHERCHES: list[dict] = [
    {"term": str(r["terme"]), "ft": r.get("langue", "fr") == "fr"}
    for r in _RECHERCHES["recherches"]
]

# --- Pré-tri -------------------------------------------------------------------
PRE_TRI_MOTIFS_TITRE: list[str] = [str(m) for m in (_EXCLUSIONS.get("motifs_titre") or [])]
PRE_TRI_EXPRESSIONS: list[str] = [str(e) for e in (_EXCLUSIONS.get("expressions") or [])]

# --- Sources actives -----------------------------------------------------------
_ACTIVES = {cle: bool((v or {}).get("actif", True)) for cle, v in _SOURCES["sources"].items()}


def source_active(cle: str) -> bool:
    """Vrai si la source est activée dans config/sources.yml (absente = active)."""
    return _ACTIVES.get(cle, True)


# --- Alertes -------------------------------------------------------------------
ALERTE_NB_SOURCES: int = int(_SOURCES["alertes"]["nb_sources_en_echec"])
ALERTE_PANNE_HEURES: float = float(_SOURCES["alertes"]["panne_heures"])

# --- Collecte ------------------------------------------------------------------
_COLLECTE = _SOURCES["collecte"]
FENETRE_DEDOUBLONNAGE_JOURS: int = int(_COLLECTE["fenetre_dedoublonnage_jours"])
CHEVAUCHEMENT_HEURES: float = float(_COLLECTE["chevauchement_heures"])
FENETRE_DEFAUT_JOURS: int = int(_COLLECTE["fenetre_defaut_jours"])
MAX_DESCRIPTION_CARACTERES: int = int(_COLLECTE["max_description_caracteres"])

# --- JobSpy (Indeed, LinkedIn) -------------------------------------------------
_JOBSPY = _SOURCES["jobspy"]
ZONE_PARIS: str = str(_JOBSPY["zone_paris"])
ZONE_TELETRAVAIL: str = str(_JOBSPY["zone_teletravail"])


# --- Plafonds de volume par source (config/sources.yml, section « plafonds ») ----
_PLAFONDS = _SOURCES.get("plafonds") or {}


def plafond(cle: str, nom: str, defaut: int) -> int:
    """Plafond `nom` de la source `cle` (pages lues, résultats par recherche…)."""
    return int((_PLAFONDS.get(cle) or {}).get(nom, defaut))
