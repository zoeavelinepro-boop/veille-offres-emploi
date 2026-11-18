"""Sources spécialisées (mode, culture, création) sur des pages simulées,
reproduisant la structure relevée sur les sites en novembre 2026 (aucune requête réelle)."""
from datetime import datetime, timedelta, timezone

from veille.sources import (source_bof, source_creativeboom, source_drapers, source_dribbble, source_fashionjobs,
                            source_fashionpersonnel, source_fashionunited, source_ifyoucould, source_michaelpage,
                            source_profilculture, source_sportyjob, _mode)
from veille.sources._commun import job_posting_ld

AUJ = datetime.now(timezone.utc).date()
LD = ('<script type="application/ld+json">{"@type":"JobPosting","title":"Head of Collections","datePosted":"%s",'
      '"hiringOrganization":{"name":"Maison X"},"jobLocation":{"address":{"addressLocality":"PARIS"}},'
      '"description":"<p>Missions</p>"}</script>') % AUJ.isoformat()


class _R:
    def __init__(self, texte):
        self.text, self.content, self.status_code = texte, texte.encode(), 200

    def raise_for_status(self):
        pass


class _Ctx:
    terms_fr = ["Directrice de collection", "Directeur de création"]
    terms_en = ["Head of Collections"]
    searches = [{"term": t, "ft": True} for t in terms_fr] + [{"term": t, "ft": False} for t in terms_en]
    max_desc = 10000

    def since(self, source):
        return datetime.now(timezone.utc) - timedelta(days=2)

    def ok(self, *a):
        pass

    def error(self, *a, **k):
        raise AssertionError(a)

    def plafond(self, *a):
        pass


def _installer(monkeypatch, module, pages):
    def faux_get(session, url, **kw):
        for cle, texte in pages.items():
            if cle in url:
                return _R(texte)
        return _R("")
    monkeypatch.setattr(module, "get", faux_get, raising=False)
    monkeypatch.setattr(_mode, "get", faux_get)


def test_fashionjobs(monkeypatch):
    _installer(monkeypatch, source_fashionjobs, {
        "/s/?keyword": '<a href="/emploi/x/Head-of-collections,1.html">Head of Collections</a>'
                       '<a href="/emploi/y/Vendeur,2.html">Vendeur</a>',
        "/emploi/x/": LD})
    offres = source_fashionjobs.fetch_fashionjobs(_Ctx())
    assert [(o["title"], o["recruiter"], o["recherche"]) for o in offres] == [("Head of Collections", "Maison X", "paris")]


def test_bof(monkeypatch):
    _installer(monkeypatch, source_bof, {
        "jobsrss": '<rss><channel><item><title>Head of Collections</title>'
                   '<link>https://www.businessoffashion.com/careers/job/1/x/</link></item></channel></rss>',
        "/careers/job/": LD})
    assert len(source_bof.fetch_bof(_Ctx())) == 1


def test_fashionunited(monkeypatch):
    _installer(monkeypatch, source_fashionunited, {
        "page=": "",
        "search/a/Paris": '<a href="/fashion-jobs/head-of-collections-paris-2044001">Head of Collections</a>'
                          '<a href="/fashion-jobs/vendeur-paris-2044002">Vendeur</a>',
        "head-of-collections": LD})
    assert len(source_fashionunited.fetch_fashionunited(_Ctx())) == 1


def test_profilculture(monkeypatch):
    d = AUJ.strftime("%d/%m/%y")
    _installer(monkeypatch, source_profilculture, {
        "-page": "",
        "Emplois-Art-Design-Architecture": (
            f'<a href="/annonce/directeur-rice-de-creation-501001.html"><h6>Directeur·rice de création</h6>'
            f'<small>Studio Y</small><small>Paris 3e</small> {d}</a>'
            f'<a href="/annonce/regisseur-501002.html"><h6>Régisseur</h6><small>Z</small><small>Paris</small> {d}</a>'),
        "directeur-rice": '<div class="left_col">Missions</div>'})
    offres = source_profilculture.fetch_profilculture(_Ctx())
    assert [(o["title"], o["recruiter"], o["description"]) for o in offres] == [("Directeur·rice de création", "Studio Y", "Missions")]


RFC = AUJ.strftime("%a, %d %b %Y 10:00:00 +0000")
LD_LONDRES = LD.replace('"PARIS"', '"London"},"addressCountry":"GB","x":{"y":1')


def test_ld_tolere_les_retours_a_la_ligne_bruts():
    page = '<script type="application/ld+json">{"@type":"JobPosting","title":"A","description":"l1\nl2"}</script>'
    page = page.replace("\\n", "\n")
    assert job_posting_ld(page)["title"] == "A"


def test_lieu_hors_zone_ecarte_sauf_teletravail():
    assert not _mode.lieu_accepte("London, United Kingdom")
    assert _mode.lieu_accepte("London, United Kingdom", teletravail=True)
    assert _mode.lieu_accepte("Paris, France") and _mode.lieu_accepte("")


def test_sportyjob(monkeypatch):
    vieux = "Mon, 01 Jan 2024 10:00:00 +0000"
    flux = ('<rss xmlns:job_listing="https://x/jl"><channel>'
            f'<item><title>Directeur de création</title><link>https://sportyjob.com/job/a/</link><pubDate>{RFC}</pubDate>'
            '<description>Missions</description><job_listing:location>Paris</job_listing:location>'
            '<job_listing:company>Marque S</job_listing:company></item>'
            f'<item><title>Vendeur</title><link>https://sportyjob.com/job/b/</link><pubDate>{RFC}</pubDate></item>'
            f'<item><title>Directeur de création</title><link>https://sportyjob.com/job/c/</link><pubDate>{vieux}</pubDate></item>'
            '</channel></rss>')
    _installer(monkeypatch, source_sportyjob, {"paged=1": flux, "paged=2": "<rss><channel></channel></rss>"})
    offres = source_sportyjob.fetch_sportyjob(_Ctx())
    assert [(o["title"], o["recruiter"], o["location"]) for o in offres] == [("Directeur de création", "Marque S", "Paris")]


def test_michaelpage(monkeypatch):
    _installer(monkeypatch, source_michaelpage, {
        "/jobs/directrice-de-collection": '<a href="/job-detail/directrice-de-collection/ref/1">Directrice de collection</a>'
                                          '<a href="/job-detail/comptable/ref/2">Comptable</a>',
        "/job-detail/directrice": LD.replace("Head of Collections", "Directrice de collection")})
    offres = source_michaelpage.fetch_michaelpage(_Ctx())
    assert [o["title"] for o in offres] == ["Directrice de collection"]
    assert source_michaelpage.slug("Directeur de création") == "directeur-de-creation"


def test_fashionpersonnel_lieu_du_titre(monkeypatch):
    ld_sans_lieu = LD.replace(',"jobLocation":{"address":{"addressLocality":"PARIS"}}', "")
    _installer(monkeypatch, source_fashionpersonnel, {
        "page=": "",
        "/jobs": '<a href="/job/head-of-collections-4521">Head of Collections</a>',
        "/job/head-of-collections": "<title>Head of Collections - Paris - Fashion Personnel</title>" + ld_sans_lieu})
    offres = source_fashionpersonnel.fetch_fashionpersonnel(_Ctx())
    assert [(o["location"], o["recherche"]) for o in offres] == [("Paris", "paris")]


def test_drapers_londres_ecarte(monkeypatch):
    _installer(monkeypatch, source_drapers, {
        "page=": "",
        "/jobs": '<a href="https://www.drapersjobs.com/job/101/head-of-collections/">Head of Collections</a>'
                 '<a href="/job/102/head-of-collections-uk/">Head of Collections UK</a>',
        "/job/101/": LD, "/job/102/": LD_LONDRES})
    offres = source_drapers.fetch_drapers(_Ctx())
    assert [o["job_url"] for o in offres] == ["https://www.drapersjobs.com/job/101/head-of-collections/"]


def test_ifyoucould(monkeypatch):
    _installer(monkeypatch, source_ifyoucould, {
        "/jobs/": LD, "ifyoucouldjobs.com/": '<a href="/jobs/8812">Head of Collections</a><a href="/jobs/8813">Junior</a>'})
    assert len(source_ifyoucould.fetch_ifyoucould(_Ctx())) == 1


def test_creativeboom_filtre_sur_adresse(monkeypatch):
    _installer(monkeypatch, source_creativeboom, {
        "page-": "",
        "/jobs/head-of-collections/": LD,
        "/jobs/": '<a href="/jobs/head-of-collections/">Head of Collections at Maison X Full-time Paris View job</a>'
                  '<a href="/jobs/barista/">Barista at Café</a><a href="/jobs/page-2/">2</a>'})
    offres = source_creativeboom.fetch_creativeboom(_Ctx())
    assert [o["title"] for o in offres] == ["Head of Collections"]


def test_dribbble(monkeypatch):
    flux = ('<rss><channel>'
            f'<item><title>Maison X is hiring for a position of Head of Collections in Paris, France</title>'
            f'<link>https://dribbble.com/jobs/1-Head</link><pubDate>{RFC}</pubDate></item>'
            f'<item><title>Y is hiring for a position of Head of Collections in New York</title>'
            f'<link>https://dribbble.com/jobs/2-Head</link><pubDate>{RFC}</pubDate></item>'
            '</channel></rss>')
    _installer(monkeypatch, source_dribbble, {"jobs.rss": flux})
    offres = source_dribbble.fetch_dribbble(_Ctx())
    assert [(o["recruiter"], o["location"]) for o in offres] == [("Maison X", "Paris, France")]
