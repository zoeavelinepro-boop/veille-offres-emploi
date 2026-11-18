"""La configuration (config/*.yml) se lit et reste cohérente avec le code."""
from veille import lecture_config as config, outils, sources


def test_les_recherches_sont_chargees():
    assert len(config.RECHERCHES) > 10
    assert all({"term", "ft"} <= set(r) for r in config.RECHERCHES)


def test_toutes_les_sources_du_code_sont_dans_sources_yml():
    cles_code = {"indeed", "linkedin"} | {cle for cle, _, _ in sources.FETCHERS}
    assert cles_code == set(config._ACTIVES), "config/sources.yml et veille/sources/__init__.py ne listent pas les mêmes sources"


def test_les_plafonds_visent_des_sources_existantes_et_se_lisent():
    cles = set(config._ACTIVES)
    assert set(config._PLAFONDS) <= cles, set(config._PLAFONDS) - cles
    assert config.plafond("indeed", "resultats_par_recherche", 0) == 20
    assert config.plafond("source_inconnue", "max_pages", 7) == 7      # absent : valeur par défaut


def test_pre_tri_ecarte_stages_et_alternances_seulement():
    for titre in ("Stage chef de projet", "Stagiaire styliste", "Fashion Design Intern", "Alternance chef de produit",
                  "Apprenti modéliste"):
        assert outils.intitule_exclu(titre), titre
    for titre in ("Directrice de collection", "Freelance Creative Director", "Brand Consultant",
                  "Head of International Brand", "early stage Head of Brand", "Junior Designer", "Assistant Art Director"):
        assert not outils.intitule_exclu(titre), titre


def test_les_mots_cles_ne_sont_pas_exclus_par_le_pre_tri():
    for r in config.RECHERCHES:
        assert not outils.intitule_exclu(r["term"]), r["term"]
