"""Règle d'alerte : e-mail seulement si panne durable ou touchant plusieurs sources."""
from datetime import timedelta

from veille import suivi_sources


def _suivi(monkeypatch, heures_depuis_succes: dict):
    runs = {s: (suivi_sources.RUN_STARTED_AT - timedelta(hours=h)).isoformat() for s, h in heures_depuis_succes.items()}
    monkeypatch.setattr(suivi_sources, "_load_last_runs", lambda: runs)


def test_panne_isolee_et_recente_n_alerte_pas(monkeypatch):
    _suivi(monkeypatch, {"hip": 3})
    assert suivi_sources.sources_a_alerter(["hip"]) == []


def test_panne_de_plus_de_24h_alerte(monkeypatch):
    _suivi(monkeypatch, {"hip": 30})
    assert suivi_sources.sources_a_alerter(["hip"]) == ["hip"]


def test_trois_sources_en_echec_alertent(monkeypatch):
    _suivi(monkeypatch, {"a": 1, "b": 1, "c": 1})
    assert suivi_sources.sources_a_alerter(["a", "b", "c"]) == ["a", "b", "c"]


def test_source_jamais_reussie_alerte(monkeypatch):
    _suivi(monkeypatch, {})
    assert suivi_sources.sources_a_alerter(["nouvelle"]) == ["nouvelle"]
