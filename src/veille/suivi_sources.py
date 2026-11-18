"""État d'un passage de collecte : bilan par source, dernier succès, alertes.

Tout ce qui permet de savoir, source par source, si la collecte a fonctionné, depuis quand,
et s'il faut prévenir par e-mail. Les sources ne parlent pas directement à ce module : elles
passent par le contexte de `collecte_quotidienne.py` (`ctx.ok`, `ctx.error`, `ctx.plafond`…).

Fichiers tenus : data/etat/dernier_succes_par_source.json (lu ici). Le bilan du run est écrit par
`redaction_bilan.py`. Toutes les heures sont en UTC, explicitement : le résultat est le même sur GitHub
Actions (UTC) et sur un ordinateur à l'heure de Paris."""

import json
from datetime import datetime, timedelta, timezone

from veille import lecture_config as reglages
from veille import sources
from veille.outils import now_utc
from veille.sources.source_jobspy import SITES as JOBSPY_SITES

LAST_RUN_FILE = reglages.DERNIER_SUCCES_FILE      # dernier succès, source par source
OVERLAP_HOURS = reglages.CHEVAUCHEMENT_HEURES     # marge de chevauchement avec le dernier run
FALLBACK_DAYS = reglages.FENETRE_DEFAUT_JOURS     # fenêtre de scrape si l'état est absent ou corrompu
MAX_LOOKBACK_DAYS = reglages.FENETRE_DEDOUBLONNAGE_JOURS  # plafond de rattrapage si une source a été en panne longtemps
ALERT_PANNE_HEURES = reglages.ALERTE_PANNE_HEURES # une source en échec dont le dernier succès remonte à plus que cela déclenche l'e-mail d'échec
ALERT_NB_SOURCES = reglages.ALERTE_NB_SOURCES     # ou : au moins ce nombre de sources en échec sur le même run

# Les sources dont on suit le dernier succès (et donc la fenêtre de rattrapage).
SOURCES = [*JOBSPY_SITES, *[key for key, _, _ in sources.FETCHERS if reglages.source_active(key)]]

RUN_STARTED_AT = now_utc()          # heure de début du run, mémorisée comme "dernier succès"

PRE_TRI_STATS = {"exclues": 0, "ecartees_titre": 0}   # compteurs du run : pré-tri et filtre de titre

# =============================================================================
# BILAN PAR SOURCE
# =============================================================================
# Chaque requête est comptée, avec son succès ou son erreur. En fin de run :
#   - une source dont TOUTES les requêtes ont échoué est "en échec" : sa date
#     de dernier succès n'avance pas (ses offres seront rattrapées au prochain
#     run). Le workflow GitHub n'échoue (et n'envoie donc d'e-mail) que si
#     ALERT_NB_SOURCES sources ou plus sont en échec, ou si une source ne
#     fonctionne plus depuis plus de ALERT_PANNE_HEURES heures ; sinon c'est
#     un simple avertissement dans le résumé du run ;
#   - le bilan est écrit dans data/etat/bilan_dernier_passage.json et dans le résumé du run.

SOURCE_STATS: dict[str, dict] = {
    s: {"requetes": 0, "erreurs": 0, "offres": 0, "echec_total": False, "note": "",
        "titres_examines": 0, "titres_retenus": 0,   # filtre de titre appliqué par la source elle-même
        "ecartees_titre": 0,                          # offres écartées ensuite par le filtre de titre global
        "plafonds": 0, "plafond_detail": ""}          # nombre de fois où un plafond a coupé la collecte
    for s in SOURCES
}

def record_ok(source: str, n_offers: int) -> None:
    """Compte une requête réussie et les offres qu'elle a renvoyées."""
    st = SOURCE_STATS[source]
    st["requetes"] += 1
    st["offres"] += n_offers

def record_error(source: str, note: str = "", fatal: bool = False) -> None:
    """Compte une requête en erreur. `fatal` = la source entière est hors service
    (identifiants absents, authentification refusée, page de liste inaccessible)."""
    st = SOURCE_STATS[source]
    st["requetes"] += 1
    st["erreurs"] += 1
    if note and not st["note"]:
        st["note"] = str(note)[:200]
    if fatal:
        st["echec_total"] = True

def source_failed(source: str) -> bool:
    """Vrai si la source est hors service sur ce run."""
    st = SOURCE_STATS[source]
    return st["echec_total"] or (st["requetes"] > 0 and st["erreurs"] == st["requetes"])

def sources_a_alerter(failed: list[str]) -> list[str]:
    """Sources en échec qui justifient l'e-mail d'échec de GitHub.
    Une panne isolée et récente (la source a fonctionné il y a moins de
    ALERT_PANNE_HEURES heures) reste un simple avertissement : elle est
    rattrapée au prochain run. On alerte si ALERT_NB_SOURCES sources ou plus
    échouent ensemble, ou si une source ne fonctionne plus depuis plus de
    ALERT_PANNE_HEURES heures (ou n'a jamais fonctionné)."""
    if len(failed) >= ALERT_NB_SOURCES:
        return list(failed)
    runs = _load_last_runs()
    persistantes = []
    for src in failed:
        try:
            ancien = RUN_STARTED_AT - _parse_utc(runs[src]) > timedelta(hours=ALERT_PANNE_HEURES)
        except (KeyError, ValueError):
            ancien = True
        if ancien:
            persistantes.append(src)
    return persistantes

# =============================================================================
# DERNIER SUCCÈS, SOURCE PAR SOURCE
# =============================================================================

def _parse_utc(value: str) -> datetime:
    """Lit un horodatage ISO ; une valeur sans fuseau (ancien format, écrit sur
    GitHub Actions) est en UTC."""
    dt = datetime.fromisoformat(value.strip())
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def _load_last_runs() -> dict:
    if LAST_RUN_FILE.exists():
        try:
            return json.loads(LAST_RUN_FILE.read_text())
        except (ValueError, OSError) as e:
            print(f"  ⚠ État dernier run illisible ({e})")
    return {}

def get_last_successful_run(source: str) -> datetime:
  
    """Renvoie l'heure (UTC) du dernier run où `source` a fonctionné.
    Sert à ne récupérer que les offres apparues depuis. Si la source a été en
    panne, la fenêtre s'élargit d'elle-même pour rattraper les offres manquées,
    dans la limite de MAX_LOOKBACK_DAYS. Sans état connu : FALLBACK_DAYS."""
  
    dt = None
    runs = _load_last_runs()
    try:
        if source in runs:
            dt = _parse_utc(runs[source])
    except (ValueError, OSError) as e:
        print(f"  ⚠ Dernier succès de {source} illisible ({e}), fallback {FALLBACK_DAYS} jours")
    if dt is None:
        dt = now_utc() - timedelta(days=FALLBACK_DAYS)
    return max(dt, now_utc() - timedelta(days=MAX_LOOKBACK_DAYS))

def save_successful_runs(ok_sources: list[str]) -> None:
  
    """Enregistre l'heure de début du run comme dernier succès des sources
    qui ont fonctionné. Les sources en échec gardent leur ancienne date."""
  
    runs = _load_last_runs()
    for source in ok_sources:
        runs[source] = RUN_STARTED_AT.isoformat()
    try:
        LAST_RUN_FILE.write_text(json.dumps(runs, indent=2, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"  ⚠ Impossible d'enregistrer {LAST_RUN_FILE.name} : {e}")
