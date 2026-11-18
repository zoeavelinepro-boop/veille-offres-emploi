"""Rejoue des réponses réelles enregistrées (tests/pages_exemples/<source>.json) à la place du réseau."""
from __future__ import annotations

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

DOSSIER = Path(__file__).parent / "pages_exemples"


def sources_enregistrees() -> list[str]:
    return sorted({p.name.split(".")[0] for p in DOSSIER.glob("*.json*")})


def _lire(source: str) -> list[dict]:
    gz = DOSSIER / f"{source}.json.gz"
    if gz.exists():
        return json.loads(gzip.decompress(gz.read_bytes()).decode("utf-8"))
    return json.loads((DOSSIER / f"{source}.json").read_text(encoding="utf-8"))


class ContexteTest:
    terms_fr = ["directeur général"]
    terms_en = ["managing director"]
    searches = [{"term": "directeur général", "ft": True}, {"term": "managing director", "ft": False}]
    max_desc = 2500

    def __init__(self):
        self.erreurs: list[str] = []
        self.ok_n: int | None = None
        self.plafonds: list[str] = []

    def since(self, source):
        return datetime(2000, 1, 1, tzinfo=timezone.utc)

    def ok(self, source, n):
        self.ok_n = n

    def error(self, source, note="", fatal=False):
        self.erreurs.append(note)

    def titre(self, source, retenu):
        pass

    def plafond(self, source, detail=""):
        self.plafonds.append(detail)


def _sans_requete(url: str) -> str:
    return url.split("?", 1)[0]


def installer(monkeypatch, source: str) -> None:
    """Remplace tout appel HTTP par la lecture des réponses enregistrées de la source."""
    reponses = _lire(source)
    deja_servies: set[int] = set()

    def requete(self, method, url, **kw):
        cle = (method.upper(), _sans_requete(url))
        candidates = [i for i, r in enumerate(reponses) if (r["method"], _sans_requete(r["url"])) == cle]
        if not candidates:
            raise requests.ConnectionError(f"hors échantillon : {cle[0]} {cle[1]}")
        # Les réponses sont servies dans l'ordre ; la dernière est resservie ensuite.
        libres = [i for i in candidates if i not in deja_servies]
        i = libres[0] if libres else candidates[-1]
        deja_servies.add(i)
        r = reponses[i]
        rep = requests.Response()
        rep.status_code = r["status"]
        rep._content = r["body"].encode("utf-8")
        rep.encoding = "utf-8"
        rep.url = url
        rep.headers["content-type"] = r["content_type"]
        return rep

    monkeypatch.setattr(requests.sessions.Session, "request", requete)
    monkeypatch.setattr("time.sleep", lambda *_: None)
