"""Une collecte complète, avec des sources simulées, dans un dossier temporaire :
vérifie les chemins de data/, le fichier d'offres, le bilan et le dernier succès."""
import json

import pytest

from veille import collecte_quotidienne as collecte


@pytest.fixture
def depot_temporaire(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    return tmp_path


def _fausse_source(offres, panne=False):
    def fetch(ctx):
        if panne:
            ctx.error("fausse", "panne simulée", fatal=True)
            return []
        ctx.ok("fausse", len(offres))
        return offres
    return fetch


def _offre(titre, recruteur="Acme"):
    return {"title": titre, "recruiter": recruteur, "location": "Paris", "is_remote": False, "job_type": "",
            "min_amount": "", "max_amount": "", "currency": "", "date_posted": "2099-01-01",
            "description": "d", "job_url": f"https://exemple.org/{titre}", "site": "fausse", "recherche": "paris"}


def _lancer(monkeypatch, fetcher):
    monkeypatch.setattr(collecte, "fetch_jobspy", lambda ctx: [])
    monkeypatch.setattr(collecte.sources, "FETCHERS", [("fausse", "Fausse", fetcher)])
    monkeypatch.setattr(collecte.suivi_sources, "SOURCES", ["fausse"])
    monkeypatch.setattr(collecte.suivi_sources, "SOURCE_STATS", {"fausse": {"requetes": 0, "erreurs": 0, "offres": 0, "echec_total": False, "note": "",
                                                          "titres_examines": 0, "titres_retenus": 0, "ecartees_titre": 0,
                                                          "plafonds": 0, "plafond_detail": ""}})
    monkeypatch.setattr(collecte.suivi_sources, "record_ok", lambda s, n: collecte.suivi_sources.SOURCE_STATS[s].update(offres=n, requetes=1))
    monkeypatch.setattr(collecte.suivi_sources, "record_error", lambda s, note="", fatal=False: collecte.suivi_sources.SOURCE_STATS[s].update(echec_total=fatal, note=note, erreurs=1, requetes=1))
    collecte.main()


def test_collecte_ecrit_offres_bilan_et_dernier_succes(depot_temporaire, monkeypatch):
    offres = [_offre("Directrice de collection"), _offre("Stage assistant"), _offre("Art Director")]
    _lancer(monkeypatch, _fausse_source(offres))
    fichiers = list((depot_temporaire / "data" / "offres").glob("offres_*.json"))
    assert len(fichiers) == 1
    titres = [o["title"] for o in json.loads(fichiers[0].read_text())]
    assert titres == ["Directrice de collection", "Art Director"]   # « Stage assistant » : aucun mot-clé
    bilan = json.loads((depot_temporaire / "data" / "etat" / "bilan_dernier_passage.json").read_text())
    assert bilan["sources_en_echec"] == [] and bilan["sources_a_alerter"] == []
    assert "fausse" in json.loads((depot_temporaire / "data" / "etat" / "dernier_succes_par_source.json").read_text())


def test_panne_d_une_source_jamais_reussie_est_a_signaler(depot_temporaire, monkeypatch):
    _lancer(monkeypatch, _fausse_source([], panne=True))
    bilan = json.loads((depot_temporaire / "data" / "etat" / "bilan_dernier_passage.json").read_text())
    assert bilan["sources_en_echec"] == ["fausse"]
    assert bilan["sources_a_alerter"] == ["fausse"]       # jamais réussie : alerte
    assert "fausse" not in json.loads((depot_temporaire / "data" / "etat" / "dernier_succes_par_source.json").read_text())


def test_source_desactivee_n_est_pas_appelee(depot_temporaire, monkeypatch):
    appels = []
    monkeypatch.setattr(collecte.reglages, "source_active", lambda cle: cle != "fausse")
    _lancer(monkeypatch, lambda ctx: appels.append(1) or [])
    assert appels == []


def test_filtre_de_titre_ecarte_et_consigne_les_offres_sans_mot_cle(depot_temporaire, monkeypatch):
    offres = [_offre("Directrice de collection"), _offre("Chargé de communication")]
    _lancer(monkeypatch, _fausse_source(offres))
    fichier = next((depot_temporaire / "data" / "offres").glob("offres_*.json"))
    assert [o["title"] for o in json.loads(fichier.read_text())] == ["Directrice de collection"]
    journal = next((depot_temporaire / "data" / "etat").glob("offres_ecartees_*.csv")).read_text(encoding="utf-8")
    assert "Chargé de communication" in journal and "Directrice de collection" not in journal
    bilan = json.loads((depot_temporaire / "data" / "etat" / "bilan_dernier_passage.json").read_text())
    assert bilan["ecartees_titre"] == 1 and bilan["sources"]["fausse"]["ecartees_titre"] == 1


def test_journal_des_ecartees_ne_consigne_pas_deux_fois_la_meme_offre(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from veille import filtrage_titres as ecartees
    monkeypatch.chdir(tmp_path)
    jour = datetime(2026, 11, 7, tzinfo=timezone.utc)
    offre = {"title": "Comptable", "recruiter": "X", "location": "Paris", "job_url": "https://x/1", "site": "indeed"}
    assert ecartees.journaliser([offre], jour) == 1
    assert ecartees.journaliser([offre], jour) == 0
