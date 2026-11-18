"""LinkedIn : la page d'une offre n'est ouverte que si son intitulé correspond à un mot-clé."""
from types import SimpleNamespace

from bs4 import BeautifulSoup
from jobspy.linkedin import LinkedIn

from veille.sources import source_jobspy


def _carte(titre):
    html = (f'<li><h3 class="base-search-card__title">{titre}</h3>'
            '<h4 class="base-search-card__subtitle"><a href="https://exemple.org/c">Acme</a></h4>'
            '<span class="job-search-card__location">Paris, France</span><time datetime="2026-11-06"></time></li>')
    return BeautifulSoup(html, "html.parser")


def _linkedin():
    appels = []
    session = SimpleNamespace(get=lambda url: appels.append(url) or (_ for _ in ()).throw(RuntimeError("hors test")))
    ln = LinkedIn.__new__(LinkedIn)
    ln.scraper_input = SimpleNamespace(fetch_description=True, description_format=None, country_indeed=None)
    ln.base_url = "https://exemple.org"
    ln.session = session
    ln.log = SimpleNamespace(warning=lambda *a, **k: None)
    return ln, appels


def test_la_page_n_est_ouverte_que_pour_un_titre_retenu(monkeypatch):
    monkeypatch.setattr(source_jobspy, "_MOTS_CLES", ["directrice de collection"])
    ln, appels = _linkedin()
    offre = ln._process_job(_carte("Chargé de communication"), "1")
    assert appels == [] and offre.title == "Chargé de communication"
    ln._process_job(_carte("Directrice de collection"), "2")
    assert appels == ["https://exemple.org/jobs/view/2"]
