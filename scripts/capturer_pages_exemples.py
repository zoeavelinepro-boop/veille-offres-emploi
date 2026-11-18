"""Enregistre quelques vraies réponses de chaque source dans tests/pages_exemples/.

Lancé par le workflow « Capturer les pages d'exemple » (réseau ouvert GitHub).
Chaque source est appelée avec UN mot-clé ; les réponses reçues (au plus MAX_REPONSES)
sont écrites dans tests/pages_exemples/<source>.json, puis rejouées par les tests
(tests/rejeu.py) sans aucun accès réseau.

Usage : PYTHONPATH=src python scripts/capturer_pages_exemples.py [source ...]
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from veille import sources

DOSSIER = Path(__file__).resolve().parents[1] / "tests" / "pages_exemples"
MAX_REPONSES = 3          # réponses gardées par source
MAX_CARACTERES = 300_000  # taille maximale d'un corps de réponse enregistré
MAX_ELEMENTS_JSON = 5     # éléments gardés dans chaque liste d'une réponse JSON
SECRETS = re.compile(r"(?i)(key|token|secret|password|client_id|client_secret|apikey)=[^&\s]+")
URL_SANS_ENREGISTREMENT = re.compile(r"(?i)(token|oauth|connexion|login|authorize)")


def reduire_json(valeur, n=MAX_ELEMENTS_JSON):
    """Garde les n premiers éléments de chaque liste : le JSON reste valide."""
    if isinstance(valeur, list):
        return [reduire_json(v, n) for v in valeur[:n]]
    if isinstance(valeur, dict):
        return {k: reduire_json(v, n) for k, v in valeur.items()}
    return valeur


LIMITES_PAR_SOURCE: dict[str, int] = {}   # limite de taille propre à une source, si une page est très lourde


def corps_reduit(texte: str, type_contenu: str, limite: int = MAX_CARACTERES) -> tuple[str, bool]:
    if "json" in type_contenu:
        try:
            return json.dumps(reduire_json(json.loads(texte)), ensure_ascii=False), True
        except ValueError:
            pass
    return texte[:limite], len(texte) > limite


class Contexte:
    terms_fr = ["directeur général"]
    terms_en = ["managing director"]
    searches = [{"term": "directeur général", "ft": True}, {"term": "managing director", "ft": False}]
    max_desc = 2500

    def since(self, source):
        return datetime.now(timezone.utc) - timedelta(days=30)

    def ok(self, source, n):
        print(f"    ok {source} : {n}")

    def error(self, source, note="", fatal=False):
        print(f"    erreur {source} : {note}")


def capturer(cle: str, fonction) -> int:
    reponses: list[dict] = []
    reelle = requests.sessions.Session.request

    def espion(self, method, url, **kw):
        r = reelle(self, method, url, **kw)
        if len(reponses) < MAX_REPONSES and not URL_SANS_ENREGISTREMENT.search(url):
            type_contenu = r.headers.get("content-type", "")
            corps, reduit = corps_reduit(r.text, type_contenu, LIMITES_PAR_SOURCE.get(cle, MAX_CARACTERES))
            reponses.append({"method": method.upper(), "url": SECRETS.sub(r"\1=XXX", url),
                             "status": r.status_code, "content_type": type_contenu,
                             "reduit": reduit, "body": corps})
        return r

    requests.sessions.Session.request = espion
    try:
        offres = fonction(Contexte())
    except Exception as e:  # une source en panne ne doit pas bloquer les autres
        print(f"  ✗ {cle} : {type(e).__name__}: {e}")
        offres = []
    finally:
        requests.sessions.Session.request = reelle
    if reponses:
        DOSSIER.mkdir(parents=True, exist_ok=True)
        contenu = json.dumps(reponses, ensure_ascii=False, indent=1).encode("utf-8")
        for ancien in DOSSIER.glob(f"{cle}.json*"):
            ancien.unlink()
        if len(contenu) > 1_500_000:      # gros fichier : compressé pour alléger le dépôt
            (DOSSIER / f"{cle}.json.gz").write_bytes(gzip.compress(contenu))
        else:
            (DOSSIER / f"{cle}.json").write_bytes(contenu)
    print(f"  {cle} : {len(reponses)} réponses enregistrées, {len(offres)} offres produites")
    return len(reponses)


def main() -> None:
    voulues = set(sys.argv[1:])
    for cle, libelle, fonction in sources.FETCHERS:
        if voulues and cle not in voulues:
            continue
        print(f"\n{libelle}…")
        capturer(cle, fonction)


if __name__ == "__main__":
    main()
