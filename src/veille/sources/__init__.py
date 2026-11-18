"""Sources d'offres hors JobSpy (Indeed et LinkedIn : source_jobspy.py).

Une source = un fichier de ce dossier, avec une fonction `fetch_<source>(ctx)`
qui renvoie une liste d'offres au format standard (title, recruiter, location,
is_remote, job_type, min_amount, max_amount, currency, date_posted, description,
job_url, site, recherche ; voir `record` dans _commun.py).

Chaque source ne connaît pas le reste du programme : la collecte lui passe un
objet `ctx` qui fournit
  - ctx.since(source) -> datetime UTC : date du dernier succès de la source
    (moins la marge de chevauchement) ;
  - ctx.ok(source, n) / ctx.error(source, note, fatal=False) : bilan par source ;
  - ctx.terms_fr / ctx.terms_en : mots-clés de recherche (listes de str) ;
  - ctx.searches : la liste complète des recherches (dictionnaires term / ft) ;
  - ctx.max_desc : longueur maximale des descriptions.

Nom des fichiers : celui de la clé de la source dans config/sources.yml (`hip.py` pour `hip`) ;
si la clé commence par un chiffre (Python n'accepte pas un module `80000hours`), le fichier prend
le préfixe `s_` (`80000hours.py`).

Pour ajouter une source : voir docs/ajouter-une-source.md.
"""

from veille.sources import (
    source_bof,
    source_creativeboom,
    source_drapers,
    source_dribbble,
    source_fashionjobs,
    source_fashionpersonnel,
    source_fashionunited,
    source_france_travail,
    source_hellowork,
    source_ifyoucould,
    source_michaelpage,
    source_profilculture,
    source_sportyjob,
    source_wttj,
)

# Ordre d'appel et libellés, utilisés par la collecte : (clé, libellé, fonction).
# La clé est celle de config/sources.yml, du bilan et de la date de dernier succès.
FETCHERS = [
    ("france_travail", "France Travail", source_france_travail.fetch_france_travail),
    ("wttj", "Welcome to the Jungle", source_wttj.fetch_wttj),
    ("hellowork", "Hellowork", source_hellowork.fetch_hellowork),
    ("fashionjobs", "FashionJobs (FashionNetwork)", source_fashionjobs.fetch_fashionjobs),
    ("bof", "BoF Careers", source_bof.fetch_bof),
    ("fashionunited", "FashionUnited", source_fashionunited.fetch_fashionunited),
    ("profilculture", "ProfilCulture", source_profilculture.fetch_profilculture),
    ("sportyjob", "SportyJob", source_sportyjob.fetch_sportyjob),
    ("michaelpage", "Michael Page", source_michaelpage.fetch_michaelpage),
    ("fashionpersonnel", "Fashion Personnel", source_fashionpersonnel.fetch_fashionpersonnel),
    ("drapers", "Drapers Jobs", source_drapers.fetch_drapers),
    ("ifyoucould", "If You Could Jobs", source_ifyoucould.fetch_ifyoucould),
    ("creativeboom", "Creative Boom", source_creativeboom.fetch_creativeboom),
    ("dribbble", "Dribbble Jobs", source_dribbble.fetch_dribbble),
]
