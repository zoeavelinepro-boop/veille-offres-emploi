"""Filtre de titre (veille.outils.titre_correspond), sur des mots-clés du type de ceux de config/mots-recherches.yml."""
from veille.outils import titre_correspond

TERMES = ["Directrice de collection", "Directeur de collection", "Head of Design", "Brand Manager",
          "Art Director"]


def test_tous_les_mots_du_terme_doivent_figurer():
    assert titre_correspond("Directrice de collection prêt-à-porter", TERMES)
    assert not titre_correspond("Directrice commerciale", TERMES)     # « collection » manque


def test_mots_vides_accents_et_pluriel_ignores():
    assert titre_correspond("Head of Design Studio", TERMES)          # « of » ignoré
    assert titre_correspond("Brand Managers", TERMES)                 # singulier / pluriel
    assert titre_correspond("DIRECTRICE DE COLLECTION H/F", TERMES)   # casse et suffixe ignorés


def test_ordre_indifferent():
    assert titre_correspond("Design, Head of", TERMES)


def test_feminin_non_unifie():
    assert not titre_correspond("Directrice de collection", ["Directeur de collection"])
    assert titre_correspond("Directeur·rice de collection", ["Directeur de collection"])


def test_rien_ne_correspond_sans_terme_ou_sans_titre():
    assert not titre_correspond("Art Director", [])
    assert not titre_correspond("", TERMES)
