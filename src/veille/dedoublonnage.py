"""Dédoublonnage : ne pas reproposer une offre déjà vue, et gérer la durée de conservation des fichiers.

  - `merge_unique` : retire les doublons entre sources au sein d'un même run ;
  - `load_recent_seen_pairs` : couples (titre, recruteur) des offres collectées ces N derniers jours ;
  - `load_known_urls` : tous les liens déjà collectés, notés ou enregistrés dans Notion, sans limite de date ;
  - `prune_old_files` : supprime les fichiers d'offres plus anciens que la fenêtre de dédoublonnage.
La fenêtre (N jours) est réglée dans config/sources.yml."""

import csv
import json
from datetime import datetime, timedelta

from veille import lecture_config as reglages
from veille.outils import dedup_key, now_utc

OFFRES_DIR = reglages.OFFRES_DIR                  # offres collectées : un fichier JSON par run
DEDUP_WINDOW_DAYS = reglages.FENETRE_DEDOUBLONNAGE_JOURS    # fenêtre du dédoublonnage historique


def merge_unique(records: list[dict], new_offers: list[dict], source_label: str) -> None:
  
    """Ajoute à `records` les offres absentes de la liste actuelle."""
  
    # 1. Calcule l'ensemble des clés de dédup déjà présentes dans `records`.
    existing = {dedup_key(r) for r in records}
    # 2. Filtre `new_offers` pour ne garder que celles dont la clé est nouvelle.
    new = [o for o in new_offers if dedup_key(o) not in existing]
    # 3. Étend `records` (modifié sur place) et logge un résumé.
    records.extend(new)
    dups = len(new_offers) - len(new)
    print(f"  → {len(new)} offres {source_label} ajoutées ({dups} doublons filtrés)")


# =============================================================================
# DÉDOUBLONNAGE HISTORIQUE (30 DERNIERS JOURS)
# =============================================================================
# But : ne pas reproposer une offre déjà vue dans un run précédent récent.
# On lit les fichiers offres_YYYY-MM-DD*.json des 30 derniers jours
# (aujourd'hui compris) et on accumule l'ensemble des clés (titre, recruteur).
# Cet ensemble est ensuite utilisé en fin de main() pour filtrer les offres.

def prune_old_files() -> None:
    """Supprime les fichiers d'offres plus anciens que la fenêtre de
    dédoublonnage (ils ne servent plus à rien) et retire de
    data/notation/fichiers_notes.json les fichiers qui n'existent plus."""
    cutoff = now_utc().date() - timedelta(days=DEDUP_WINDOW_DAYS + 1)
    removed = 0
    for file in OFFRES_DIR.glob("offres_*.json"):
        try:
            file_date = datetime.strptime(file.stem.replace("offres_", "")[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if file_date < cutoff:
            file.unlink()
            removed += 1
    state_file = reglages.FICHIERS_NOTES_FILE
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            state["fichiers_traites"] = sorted(f for f in state.get("fichiers_traites", []) if (OFFRES_DIR / f).exists())
            state["en_cours"] = {f: n for f, n in state.get("en_cours", {}).items() if (OFFRES_DIR / f).exists()}
            state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except (OSError, ValueError) as e:
            print(f"  ⚠ notation/fichiers_notes.json non nettoyé : {e}")
    if removed:
        print(f"  → {removed} fichiers d'offres de plus de {DEDUP_WINDOW_DAYS + 1} jours supprimés")



def load_recent_seen_pairs() -> set[tuple[str, str]]:
  
    """Renvoie l'ensemble des clés de dédup déjà vues sur les 30 derniers jours.
    On parcourt OFFRES_DIR à la recherche des fichiers offres_*.json,
    on extrait la date depuis le nom, et on charge les offres des fichiers
    dont la date est dans la fenêtre [today - 30j, today]. Le jour courant
    est inclus : un 2e run dans la journée ne doit pas reproposer les
    offres du 1er (le fichier du run en cours n'existe pas encore).
    Robuste : un fichier illisible ou un nom mal formé est ignoré
    silencieusement, sans bloquer le run."""
  
    today = now_utc().date()
    cutoff = today - timedelta(days=DEDUP_WINDOW_DAYS)
    seen: set[tuple[str, str]] = set()

    # Premier run : OFFRES_DIR n'existe pas encore, rien à charger.
    if not OFFRES_DIR.exists():
        return seen

    for file in OFFRES_DIR.glob("offres_*.json"):
        # Extraire la date depuis le nom "offres_YYYY-MM-DD.json".
        try:
            date_str = file.stem.replace("offres_", "")[:10]  # "YYYY-MM-DD" ou "YYYY-MM-DD_HHMM"
            file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            # Nom de fichier non conforme : on ignore.
            continue

        # Garder uniquement les fichiers dans la fenêtre [cutoff, today].
        if file_date < cutoff or file_date > today:
            continue

        # Charger les offres et accumuler les clés non vides.
        try:
            with open(file, encoding="utf-8") as f:
                offers = json.load(f)
            for o in offers:
                key = dedup_key(o)
                if key[0] and key[1]:  # titre ET recruteur non vides
                    seen.add(key)
        except Exception as e:
            print(f"  ⚠ Lecture {file.name} échouée : {e}")
            continue

    return seen

def load_known_urls() -> set[str]:
    """Renvoie tous les liens d'offres déjà connus, sans limite de date :
    offres de toutes les collectes précédentes (data/offres/offres_*.json), lignes
    des journaux de notation (data/notation/journaux/journal_*.csv) et relevé des fiches
    Notion (data/notation/references/offres_notion_connues.csv). Une offre dont le lien y figure a
    déjà été proposée à la notation : inutile de la lui redonner.
    Robuste : un fichier illisible est ignoré, sans bloquer le run."""
    known: set[str] = set()
    if not OFFRES_DIR.exists():
        return known
    for file in OFFRES_DIR.glob("offres_*.json"):
        try:
            with open(file, encoding="utf-8") as f:
                for o in json.load(f):
                    url = str(o.get("job_url") or "").strip()
                    if url:
                        known.add(url)
        except Exception as e:
            print(f"  ⚠ Lecture {file.name} échouée : {e}")
    csv_files = list(reglages.JOURNAUX_DIR.glob("journal_*.csv"))
    csv_files.append(reglages.OFFRES_NOTION_CONNUES_FILE)
    for file in csv_files:
        if not file.exists():
            continue
        try:
            with open(file, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f, delimiter=";"):
                    url = str(row.get("lien") or "").strip()
                    if url:
                        known.add(url)
        except Exception as e:
            print(f"  ⚠ Lecture {file.name} échouée : {e}")
    return known
