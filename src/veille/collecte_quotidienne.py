"""
veille.collecte_quotidienne — Agrégateur d'offres d'emploi multi-sources.

Pour chaque mot-clé défini dans config/mots-recherches.yml, on interroge plusieurs sources d'offres d'emploi
indépendamment : si l'une tombe en erreur, les autres continuent à tourner.

Sources interrogées :
  - JobSpy (Indeed + LinkedIn), ici — chaque site est appelé isolément ;
  - toutes les autres (France Travail, Welcome to the Jungle, Hellowork,
    FashionJobs, BoF Careers, FashionUnited, ProfilCulture, SportyJob, Michael Page,
    Fashion Personnel, Drapers, If You Could, Creative Boom, Dribbble) dans veille/sources/,
    une par fichier, appelées dans l'ordre de sources.FETCHERS.
Le découpage : l'état et les alertes (suivi_sources.py), le dédoublonnage (dedoublonnage.py), le bilan (redaction_bilan.py),
les petits outils (outils.py) ; ce fichier ne fait que l'enchaînement des étapes ;
les réglages (mots-clés, exclusions, sources actives, seuils) dans config/.

Lancement, depuis la racine du dépôt : PYTHONPATH=src python -m veille.collecte_quotidienne

Pipeline (voir main()) :
  - charge la liste des couples (titre, recruteur) d'offres déjà vues sur les
    DEDUP_WINDOW_DAYS jours précédents (dédoublonnage historique) ;
  - récupère les offres de chaque source, et les dédoublonne entre elles ;
  - dédoublonne les offres déjà vues ;
  - écrit le résultat dans data/offres/offres_YYYY-MM-DD.json (ou
    data/offres/offres_YYYY-MM-DD_HHMM.json pour un 2e run dans la journée) ;
  - écrit le bilan par source dans data/etat/bilan_dernier_passage.json.

L'heure du dernier succès de chaque source est conservée dans
data/etat/dernier_succes_par_source.json pour ne récupérer que les offres récentes
(avec 1 h de chevauchement de sécurité). Une source en panne garde son
ancienne date : ses offres sont rattrapées au run suivant.
Toutes les heures sont en UTC.

Conçu pour tourner dans GitHub Actions (réseau ouvert).
"""

import json
import pandas as pd                        # JobSpy renvoie ses résultats sous forme de DataFrame à manipuler
from datetime import datetime, timedelta   # fenêtres temporelles des sources
from veille import lecture_config as reglages     # réglages lus dans config/ et chemins de data/
from veille import dedoublonnage, redaction_bilan, suivi_sources
from veille import sources                 # les sources hors JobSpy (France Travail, WTTJ, sources mode…)
from veille import filtrage_titres   # journal des offres écartées par le filtre de titre
from veille.sources.source_jobspy import fetch_jobspy   # Indeed et LinkedIn, via la bibliothèque JobSpy
from veille.outils import MAX_DESC_CHARS, dedup_key, intitule_exclu, now_utc

OFFRES_DIR = reglages.OFFRES_DIR                  # offres collectées : un fichier JSON par run
DEDUP_WINDOW_DAYS = reglages.FENETRE_DEDOUBLONNAGE_JOURS

# =============================================================================
# CONFIG
# =============================================================================
# Les mots-clés de recherche sont dans config/mots-recherches.yml (voir le commentaire
# en tête de ce fichier sur le fonctionnement approximatif des moteurs).
# Chaque entrée : {"term": mot-clé, "ft": True si terme français, envoyé aussi à
# France Travail}. Les autres sources reçoivent tous les termes.
SEARCHES = reglages.RECHERCHES

# Colonnes du record final écrit dans le JSON.
# Toutes les sources se conforment à ce schéma (titre, recruteur, lieu, télétravail, type de contrat, salaire, etc.).
JOBSPY_OUTPUT_COLUMNS = (
    "title",
    "recruiter",
    "location",
    "is_remote",
    "job_type",
    "min_amount",
    "max_amount",
    "currency",
    "date_posted",
    "description",
    "job_url",
    "site",
    "recherche",
)

# Champ "recherche" de chaque offre : la recherche qui l'a trouvée.
#   - "paris"       : recherche géographique autour de Paris (≤ 20-50 km) ;
#   - "teletravail" : recherche 100 % télétravail, partout en France — une
#     offre en région n'est là que parce qu'elle est annoncée à distance ;
# La notation s'en sert pour écarter les offres en région dont le télétravail
# complet n'est pas confirmé.

# Identifiants France Travail (optionnels).
# Si non fournis via variables d'environnement, on saute simplement cette source — pas d'erreur fatale.

class SupplementaryContext:
    """Ce dont le module sources.py a besoin du script."""
    terms_fr = [e["term"] for e in SEARCHES if e["ft"]]
    terms_en = [e["term"] for e in SEARCHES if not e["ft"]]
    searches = SEARCHES
    max_desc = MAX_DESC_CHARS

    def since(self, source: str) -> datetime:
        return suivi_sources.get_last_successful_run(source) - timedelta(hours=suivi_sources.OVERLAP_HOURS)

    def ok(self, source: str, n: int) -> None:
        suivi_sources.record_ok(source, n)

    def error(self, source: str, note: str = "", fatal: bool = False) -> None:
        suivi_sources.record_error(source, note, fatal=fatal)

    def titre(self, source: str, retenu: bool) -> None:
        """Compte un titre examiné par le filtre de mots-clés d'une source sans moteur de recherche."""
        st = suivi_sources.SOURCE_STATS[source]
        st["titres_examines"] += 1
        st["titres_retenus"] += int(retenu)

    def plafond(self, source: str, detail: str = "") -> None:
        """Signale qu'un plafond (pages, résultats, détails) a coupé la collecte de la source."""
        st = suivi_sources.SOURCE_STATS[source]
        st["plafonds"] += 1
        if detail and not st["plafond_detail"]:
            st["plafond_detail"] = str(detail)[:160]


# =============================================================================
# MAIN
# =============================================================================
def main() -> None:
    """Pipeline principal : agrège les sources, dédoublonne, exporte le JSON.
    Étapes (chacune isolée par try/except dans son fetch_* respectif, donc
    une source en échec ne bloque jamais les autres) :
      1. Préparer le dossier de sortie + le timestamp du jour.
      2. Charger l'index des offres déjà vues sur les 30 derniers jours.
      3. JobSpy (Indeed + LinkedIn) → DataFrames pandas → records.
      4. France Travail API → records (si credentials présents).
      5-6. Autres sources de sources.FETCHERS → records.
      7. Filtrer les records déjà vus historiquement.
      8. Écrire data/offres/offres_YYYY-MM-DD[_HHMM].json en atomique.
      9. Mémoriser le dernier succès de chaque source qui a fonctionné,
         écrire le bilan par source."""
    # --- 1. Préparation ---
    OFFRES_DIR.mkdir(parents=True, exist_ok=True)        # crée data/offres/ si besoin
    reglages.ETAT_DIR.mkdir(parents=True, exist_ok=True)  # crée data/etat/ si besoin

    dedoublonnage.prune_old_files()
    print(f"[{now_utc():%H:%M:%S}] Chargement du dédoublonnage historique ({DEDUP_WINDOW_DAYS} jours)…")
    seen = dedoublonnage.load_recent_seen_pairs()
    print(f"  → {len(seen)} couples (titre, recruteur) déjà vus sur la fenêtre")

    # `records` accumule progressivement les offres de toutes les sources.
    records: list[dict] = []

    # --- 3. JobSpy ---
    # Cas particulier : JobSpy renvoie des DataFrames pandas, pas des dicts.
    # Il faut donc concaténer, dédoublonner sur (title, company), nettoyer
    # les NaN, renommer "company" en "recruiter", puis convertir en records.
    print(f"[{now_utc():%H:%M:%S}] Scraping JobSpy (site par site)…")
    ctx = SupplementaryContext()
    dfs = fetch_jobspy(ctx)
    if dfs:
        # Concaténation verticale (un DataFrame unique par-dessus tous les sites).
        df = pd.concat(dfs, ignore_index=True)
        # Une offre trouvée par les deux recherches garde "paris" (tri stable :
        # "paris" < "teletravail", et drop_duplicates garde la première).
        if "recherche" in df.columns:
            df = df.sort_values("recherche", kind="stable")
        # Dédoublonnage avant rename : la colonne s'appelle encore "company".
        df = df.drop_duplicates(subset=["title", "company"], keep="first")
        # Aligner le nom de colonne avec le schéma standard (et avec Notion en aval).
        df = df.rename(columns={"company": "recruiter"})
        # Les NaN pandas font planter json.dump → on les remplace par "".
        for col in ("title", "recruiter", "location", "job_url", "job_type"):
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str)
        if "description" in df.columns:
            df["description"] = df["description"].fillna("").astype(str).str[:MAX_DESC_CHARS]
        # Ne garder que les colonnes du schéma standard qui existent réellement
        # (tous les sites ne renvoient pas exactement les mêmes champs).
        keep = [c for c in JOBSPY_OUTPUT_COLUMNS if c in df.columns]
        jobspy_records = df[keep].to_dict("records")
        records.extend(jobspy_records)
        print(f"  → {len(jobspy_records)} offres JobSpy (dédoublonnées)")

    # --- 4. Autres sources (veille/sources/ : France Travail, WTTJ, Hellowork, sources mode et culture) ---
    for key, label, fetch in sources.FETCHERS:
        if not reglages.source_active(key):
            print(f"\n[{now_utc():%H:%M:%S}] {label} : désactivée dans config/sources.yml")
            continue
        print(f"\n[{now_utc():%H:%M:%S}] {label}…")
        try:
            offers = fetch(ctx)
        except Exception as e:
            print(f"  ✗ {label} : {type(e).__name__}: {str(e)[:150]}")
            suivi_sources.record_error(key, f"{type(e).__name__}: {str(e)[:150]}", fatal=True)
            continue
        for o in offers:
            if o.get("description"):
                o["description"] = str(o["description"])[:MAX_DESC_CHARS]
        dedoublonnage.merge_unique(records, offers, label)

    # --- 6 ter. Pré-tri sur l'intitulé (stage, alternance, junior, assistant) ---
    before = len(records)
    records = [r for r in records if not intitule_exclu(r.get("title"))]
    suivi_sources.PRE_TRI_STATS["exclues"] = before - len(records)
    print(f"\n[{now_utc():%H:%M:%S}] Pré-tri sur l'intitulé : {before - len(records)} offres écartées (stage, junior, assistant, expressions exclues)")

    # --- 6 quater. Filtre de titre, pour toutes les sources ---
    # Seules les offres dont l'intitulé contient les mots d'un terme de config/mots-recherches.yml sont
    # gardées. Les moteurs d'Indeed, LinkedIn, etc. cherchent aussi dans la description : sans ce
    # filtre, la plupart des offres reçues n'ont aucun rapport avec les postes visés.
    # Les offres écartées sont consignées dans data/etat/offres_ecartees_AAAA-MM.csv.
    termes = [e["term"] for e in SEARCHES]
    gardees, ecartees = filtrage_titres.filtrer(records, termes)
    for r in ecartees:
        if r.get("site") in suivi_sources.SOURCE_STATS:
            suivi_sources.SOURCE_STATS[r["site"]]["ecartees_titre"] += 1
    suivi_sources.PRE_TRI_STATS["ecartees_titre"] = len(ecartees)
    ajoutees = filtrage_titres.journaliser(ecartees, suivi_sources.RUN_STARTED_AT)
    records = gardees
    print(f"[{now_utc():%H:%M:%S}] Filtre de titre : {len(ecartees)} offres écartées (aucun mot-clé dans l'intitulé), "
          f"{len(gardees)} gardées ; {ajoutees} nouvelles consignées dans {filtrage_titres.chemin(suivi_sources.RUN_STARTED_AT)}")

    # --- 7. Dédoublonnage historique (30 derniers jours) ---
    # On retire les offres dont la clé est déjà présente dans un fichier JSON
    # antérieur à aujourd'hui. C'est ce qui évite de proposer 10 fois la même
    # offre à Claude au fil des jours.
    before = len(records)
    records = [r for r in records if dedup_key(r) not in seen]
    filtered = before - len(records)
    print(f"\n[{now_utc():%H:%M:%S}] Dédoublonnage historique : {filtered} offres déjà vues sur les {DEDUP_WINDOW_DAYS} derniers jours retirées")

    # --- 7 bis. Dédoublonnage par lien, sans limite de date ---
    # Toute offre dont le lien a déjà été collecté, noté ou enregistré dans
    # Notion est retirée : la notation n'a plus à relire la base Notion.
    known_urls = dedoublonnage.load_known_urls()
    before = len(records)
    records = [r for r in records if str(r.get("job_url") or "").strip() not in known_urls]
    print(f"[{now_utc():%H:%M:%S}] Dédoublonnage par lien : {before - len(records)} offres déjà connues retirées ({len(known_urls)} liens connus)")

    # Dernier passage : la normalisation (H/F, accents…) peut révéler des
    # doublons entre offres de ce run qui n'étaient pas identiques au caractère près.
    unique: list[dict] = []
    keys: set[tuple[str, str]] = set()
    for r in records:
        k = dedup_key(r)
        if k not in keys:
            keys.add(k)
            unique.append(r)
    if len(unique) < len(records):
        print(f"  → {len(records) - len(unique)} doublons supplémentaires retirés (H/F, accents, ponctuation)")
    records = unique

    # Nom du fichier : offres_YYYY-MM-DD.json pour le 1er run du jour.
    # Un 2e run le même jour écrit offres_YYYY-MM-DD_HHMM.json (UTC) au lieu
    # d'écraser le fichier du matin.
    day = suivi_sources.RUN_STARTED_AT.strftime("%Y-%m-%d")
    out_path = OFFRES_DIR / f"offres_{day}.json"
    if out_path.exists():
        out_path = OFFRES_DIR / f"offres_{day}_{suivi_sources.RUN_STARTED_AT:%H%M}.json"
    tmp_path = out_path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2, default=str)
    tmp_path.replace(out_path)  # rename atomique (POSIX et Windows ≥ 10)

    # Bilan par source + dernier succès (seulement pour les sources qui ont fonctionné).
    failed = [src for src in suivi_sources.SOURCES if suivi_sources.source_failed(src)]
    alertes = suivi_sources.sources_a_alerter(failed)   # à lire AVANT d'enregistrer les nouveaux succès
    suivi_sources.save_successful_runs([src for src in suivi_sources.SOURCES if src not in failed])
    redaction_bilan.write_run_report(out_path, len(records), failed, alertes)

    print(f"\n✅ {len(records)} offres totales écrites dans {out_path}")
    if failed:
        print(f"⚠ Sources en échec : {', '.join(failed)}")



if __name__ == "__main__":
    main()
