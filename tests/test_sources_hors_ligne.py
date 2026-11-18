"""Chaque source lit des réponses réelles enregistrées (tests/pages_exemples/) sans accès réseau.

Si un site change sa page, ce test passe tant que le fichier enregistré n'est pas renouvelé :
relancer le workflow « Capturer les pages d'exemple » (GitHub → Actions) pour le renouveler,
puis ce test indique si le code sait encore lire la nouvelle page."""
import pytest

from rejeu import ContexteTest, installer, sources_enregistrees
from veille import sources

# Sources dont l'échantillon enregistré ne contient aucune offre retenue (filtre France / télétravail).
SANS_OFFRE_RETENUE: set[str] = set()
FONCTIONS = {cle: fonction for cle, _, fonction in sources.FETCHERS}


@pytest.mark.parametrize("cle", sources_enregistrees())
def test_source_lit_ses_pages_enregistrees(cle, monkeypatch):
    installer(monkeypatch, cle)
    # Le filtre par mots-clés est testé à part (test_filtre_titres.py) : ici on vérifie la lecture des pages.
    for module in vars(sources).values():
        if hasattr(module, "titre_retenu"):
            monkeypatch.setattr(module, "titre_retenu", lambda ctx, titre, source="": True)
    if cle == "france_travail":   # le jeton d'accès n'est pas enregistré
        monkeypatch.setattr(sources.source_france_travail, "fetch_france_travail_token", lambda ctx=None: "jeton-test")
    ctx = ContexteTest()
    offres = FONCTIONS[cle](ctx)
    # Seules quelques pages sont enregistrées par source : les autres sont « hors échantillon » (normal).
    erreurs = [e for e in ctx.erreurs if "hors échantillon" not in e]
    assert not erreurs, f"{cle} : erreurs {erreurs[:3]}"
    if cle in SANS_OFFRE_RETENUE:
        assert ctx.ok_n, f"{cle} : aucune offre lue dans la page enregistrée"
        return
    assert offres, f"{cle} : lecture correcte mais aucune offre retenue"
    for o in offres:
        assert o["title"], f"{cle} : offre sans intitulé"
        assert o["job_url"].startswith("http"), f"{cle} : offre sans lien"
    assert o["site"]
