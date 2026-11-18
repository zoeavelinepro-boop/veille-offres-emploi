"""Outils partagés par les sources mode, luxe et création (FashionJobs, BoF Careers,
FashionUnited, ProfilCulture, SportyJob, Michael Page, Drapers, Fashion Personnel,
If You Could, Creative Boom, Dribbble) : zone acceptée, liens d'une liste, lecture
du JSON-LD d'une offre."""

from __future__ import annotations

import html as html_lib
import re
from datetime import datetime, timedelta, timezone

from veille.sources._commun import get, is_idf, job_posting_ld, ld_location, ld_salary, record, strip_html

# Lieux acceptés quand la plateforme est internationale : France, Paris, Europe ou télétravail.
# Un lieu inconnu est gardé (la notation tranche). Un lieu connu hors de cette zone
# (Londres, New York…) est écarté, sauf offre en télétravail.
MODE_OK_LOCATIONS = ("france", "paris", "île-de-france", "ile-de-france", "remote", "télétravail",
                     "teletravail", "europe", "emea", "anywhere", "worldwide")


def lieu_accepte(location: str, teletravail: bool = False) -> bool:
    low = (location or "").lower()
    return teletravail or not low or is_idf(location) or any(w in low for w in MODE_OK_LOCATIONS)


def liens(page_html: str, motif: re.Pattern, base: str = "") -> list[tuple[str, str]]:
    """Liens d'une page de liste dont le chemin correspond à `motif` : [(url, texte)], sans doublon.

    Le domaine `base` est retiré avant comparaison puis rajouté à l'URL renvoyée."""
    vus, sortie = set(), []
    for m in re.finditer(r'<a\b[^>]*?href="([^"]+)"[^>]*>(.*?)</a>', page_html, re.S | re.I):
        chemin = html_lib.unescape(m.group(1)).split("#")[0].split("?")[0]
        if base and chemin.startswith(base):
            chemin = chemin[len(base):]
        if not motif.match(chemin) or chemin in vus:
            continue
        vus.add(chemin)
        sortie.append((base + chemin, strip_html(m.group(2)).replace("\n", " ").strip()))
    return sortie


def titre_depuis_slug(url: str) -> str:
    """« /jobs/creative-director-paris-123 » → « creative director paris 123 » (pour le filtre de titre)."""
    dernier = [p for p in url.rstrip("/").split("/") if p][-1]
    return re.sub(r"[-_]+", " ", dernier)


def page_detail(session, url: str) -> tuple[str, dict]:
    """(HTML, JSON-LD JobPosting) de la page de l'offre ; ("", {}) si erreur."""
    try:
        d = get(session, url)
        if d.status_code != 200:
            return "", {}
        return d.text, job_posting_ld(d.text)
    except Exception:
        return "", {}


def detail_ld(session, url: str) -> dict:
    """JSON-LD JobPosting de la page de l'offre ({} si absent ou erreur)."""
    return page_detail(session, url)[1]


def trop_ancienne(date_iso: str, since: datetime) -> bool:
    try:
        return datetime.fromisoformat(date_iso[:10]).replace(tzinfo=timezone.utc) < since - timedelta(days=1)
    except ValueError:
        return False


def offre_depuis_ld(ld: dict, url: str, title: str, site: str, since: datetime, max_desc: int,
                    location: str = "", recruteur: str = "", description: str = "",
                    date_posted: str = "") -> dict | None:
    """Offre au format standard à partir du JSON-LD ; None si trop ancienne ou hors zone.

    location / recruteur / description / date_posted : valeurs de repli quand le JSON-LD
    ne les donne pas (lues dans la liste ou le flux)."""
    posted = (ld.get("datePosted") or date_posted or "")[:10]
    if posted and trop_ancienne(posted, since):
        return None
    location = ld_location(ld) or location
    remote = ld.get("jobLocationType") == "TELECOMMUTE" or bool(
        re.search(r"remote|télétravail|teletravail|anywhere", location or "", re.I))
    if not lieu_accepte(location, remote):
        return None
    org = ld.get("hiringOrganization") or {}
    mn, mx, cur = ld_salary(ld)
    return record(
        title=title or ld.get("title", ""),
        recruiter=(org.get("name") if isinstance(org, dict) else "") or recruteur or "",
        location=location, is_remote=remote,
        job_type=ld.get("employmentType", "") if isinstance(ld.get("employmentType"), str) else "",
        min_amount=mn, max_amount=mx, currency=cur, date_posted=posted,
        description=(strip_html(ld.get("description")) or strip_html(description))[:max_desc],
        job_url=url, site=site,
        recherche="paris" if is_idf(location) else "teletravail",
    )


def collecte_liste(ctx, source: str, session, urls_pages: list[str], motif: re.Pattern, base: str,
                   max_details: int, titre_slug: bool = False, lieu_titre_page: bool = False,
                   recruteur_defaut: str = "") -> list[dict]:
    """Collecte type « pages de liste + JSON-LD de chaque offre ».

    1. lit les pages `urls_pages` dans l'ordre (arrêt à la première page sans nouveau lien) ;
    2. garde les liens dont l'intitulé correspond aux mots-clés (texte du lien, ou
       chemin de l'URL si `titre_slug`, quand le lien englobe toute la carte) ;
    3. ouvre au plus `max_details` offres et lit leur JSON-LD.
    `lieu_titre_page` : lieu de repli lu dans le <title> de la page (« Intitulé - Lieu »).
    `recruteur_defaut` : employeur de repli (site intermédiaire : cabinet de recrutement)."""
    from veille.outils import intitule_exclu
    from veille.sources._commun import titre_retenu

    since = ctx.since(source)
    cartes, vus = [], set()
    for i, url_page in enumerate(urls_pages, 1):
        try:
            r = get(session, url_page)
            r.raise_for_status()
        except Exception as e:
            if i == 1:
                ctx.error(source, f"liste : {type(e).__name__}: {str(e)[:120]}")
            break
        nouveaux = [(u, t) for u, t in liens(r.text, motif, base) if u not in vus]
        ctx.ok(source, len(nouveaux))
        if not nouveaux:
            break
        for u, t in nouveaux:
            vus.add(u)
            titre = titre_depuis_slug(u) if titre_slug or not t else t
            if not intitule_exclu(titre) and titre_retenu(ctx, titre, source):
                cartes.append((u, "" if titre_slug else t))
    offres = []
    for u, t in cartes[:max_details]:
        page, ld = page_detail(session, u)
        lieu = ""
        if lieu_titre_page and not ld_location(ld):
            m = re.search(r"<title>([^<]*)</title>", page, re.I)
            morceaux = [x.strip() for x in re.split(r"\s[-|–]\s", html_lib.unescape(m.group(1)))] if m else []
            lieu = morceaux[1] if len(morceaux) > 2 else ""
        rec = offre_depuis_ld(ld, u, ld.get("title") or t, source, since, ctx.max_desc,
                              location=lieu, recruteur=recruteur_defaut)
        if rec and rec["title"]:
            offres.append(rec)
    if len(cartes) > max_details:
        ctx.plafond(source, f"{len(cartes)} offres, {max_details} pages de détail lues")
    print(f"    {source} → {len(vus)} offres lues, {len(offres)} retenues")
    return offres
