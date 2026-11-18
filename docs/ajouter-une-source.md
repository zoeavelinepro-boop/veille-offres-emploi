# Ajouter une plateforme

Une plateforme = un fichier dans `src/veille/sources/` + une ligne dans deux listes.

1. **Créer le fichier** `src/veille/sources/source_ma_plateforme.py` avec une fonction `fetch_ma_plateforme(ctx)`. Le fichier s'appelle `source_` + la clé de la source dans `config/sources.yml`.
   - Elle renvoie une liste d'offres créées par `record(...)` (voir `sources/_commun.py`) : `title`, `recruiter`, `location`, `is_remote`, `job_type`, `date_posted`, `description`, `job_url`, `site`, `recherche`.
   - Elle ne garde que les offres publiées depuis `ctx.since("ma_cle")`.
   - Elle signale son état avec `ctx.ok("ma_cle", nombre)` ou `ctx.error("ma_cle", "message")`. **Une source ne doit jamais faire planter la collecte** : en cas d'erreur, appeler `ctx.error` et renvoyer `[]`.
2. **L'enregistrer** dans `src/veille/sources/__init__.py` : un `import` et une ligne `("ma_cle", "Libellé", ma_plateforme.fetch_ma_plateforme)` dans `FETCHERS` (l'ordre = l'ordre d'appel).
3. **La déclarer** dans `config/sources.yml` : `ma_cle: {actif: true}`. Un test vérifie que les deux listes concordent.
4. **La tester** : copier une page réelle de la plateforme dans `tests/pages_exemples/`, puis écrire `tests/test_ma_plateforme.py` sur le modèle de `tests/test_hip.py` (la fonction `get` est remplacée par la page enregistrée : aucune requête réelle). Lancer `pytest`.
5. **Documenter** : ajouter une ligne au tableau « Plateformes interrogées » du README.
6. **Vérifier en réel** : lancer le workflow « Collecte quotidienne » à la main depuis l'onglet Actions et lire le résumé du run (une ligne par source).

Règles à respecter : lire le `robots.txt` du site et ne pas dépasser un rythme raisonnable (`PAUSE` dans `_commun.py`) ; ne jamais enregistrer de mot de passe dans le code (utiliser les secrets GitHub).

## Tester la nouvelle source hors ligne

Les tests de chaque source (`tests/test_sources_hors_ligne.py`) rejouent de vraies réponses
enregistrées dans `tests/pages_exemples/<source>.json`, sans accès réseau.

1. Ajouter la source à `FETCHERS` (`src/veille/sources/__init__.py`).
2. Lancer sur GitHub : Actions → « Capturer les pages d'exemple » → Run workflow. Le workflow
   enregistre quelques réponses de chaque source et les ajoute au dépôt.
3. Récupérer le résultat (`git pull`) et lancer `PYTHONPATH=src pytest`.

Quand un site change sa page, relancer ce workflow : le test indique alors si le code sait
encore lire la nouvelle version.
