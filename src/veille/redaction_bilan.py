"""Bilan d'un passage de collecte : fichier JSON, résumé visible dans GitHub Actions, sorties du workflow."""

import json
import os
from pathlib import Path

from veille import lecture_config as reglages
from veille import suivi_sources
from veille.sources.source_jobspy import SITES as JOBSPY_SITES

RUN_REPORT_FILE = reglages.BILAN_FILE             # bilan du dernier run, par source


def write_run_report(out_path: Path, count: int, failed: list[str], alertes: list[str]) -> None:
    """Écrit le bilan du run : data/etat/bilan_dernier_passage.json, le résumé visible dans
    l'onglet Actions de GitHub, et les sorties lues par le workflow."""
    report = {
        "run_utc": suivi_sources.RUN_STARTED_AT.isoformat(),
        "fichier": str(out_path),
        "offres_ecrites": count,
        "sources_en_echec": failed,
        "sources_a_alerter": alertes,
        "pre_tri_exclues": suivi_sources.PRE_TRI_STATS["exclues"],
        "ecartees_titre": suivi_sources.PRE_TRI_STATS["ecartees_titre"],
        "sources": suivi_sources.SOURCE_STATS,
    }
    RUN_REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    lines = ["| Source | Requêtes | Erreurs | Offres reçues | Écartées (titre) | Plafond | État |", "|---|---|---|---|---|---|---|"]
    for src in suivi_sources.SOURCES:
        st = suivi_sources.SOURCE_STATS[src]
        if src in failed:
            state = f"❌ en échec — {st['note']}"
        elif st["erreurs"]:
            state = f"⚠ erreurs partielles — {st['note']}"
        else:
            state = "✅"
        plafond = f"⚠ {st['plafonds']}× ({st['plafond_detail']})" if st["plafonds"] else "-"
        lines.append(f"| {src} | {st['requetes']} | {st['erreurs']} | {st['offres']} | {st['ecartees_titre']} | {plafond} | {state} |")
    table = "\n".join(lines)
    print("\n" + table)

    # Sorties pour GitHub Actions (ignorées en local).
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"## {count} offres écrites dans `{out_path}`\n\n{table}\n")
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as f:
            f.write(f"out_file={out_path}\n")
            f.write(f"count={count}\n")
            f.write(f"failed_sources={' '.join(failed)}\n")
            f.write(f"alert_sources={' '.join(alertes)}\n")
    for src in failed:
        niveau = "error" if src in alertes else "warning"
        print(f"::{niveau} title=Source en échec : {src}::{suivi_sources.SOURCE_STATS[src]['note'] or 'toutes les requêtes ont échoué'}")
    for src in JOBSPY_SITES:
        # JobSpy avale parfois les blocages et renvoie 0 offre sans erreur.
        if src in suivi_sources.SOURCE_STATS and src not in failed and suivi_sources.SOURCE_STATS[src]["offres"] == 0:
            print(f"::warning title={src} : 0 offre::Aucune offre reçue de {src} — possible blocage anti-robot.")


