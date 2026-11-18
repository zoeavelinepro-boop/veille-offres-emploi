"""Chaque source déclarée est appelable et au format attendu."""
from veille import sources


def test_cles_uniques_et_fonctions_appelables():
    cles = [cle for cle, _, _ in sources.FETCHERS]
    assert len(cles) == len(set(cles))
    assert all(callable(f) for _, _, f in sources.FETCHERS)
