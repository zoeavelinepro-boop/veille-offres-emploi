# Veille d'offres d'emploi

Collecte quotidienne d'offres d'emploi de direction créative, de marque et de produit (mode, lifestyle, sportswear), notation par Claude au regard de ton Profil, et enregistrement des offres pertinentes dans Notion.

Pour installer cette veille ailleurs : `docs/installation.md`. Pour ajouter une plateforme : `docs/ajouter-une-source.md`. En cas de panne : `docs/depannage.md`.

## Chaîne complète

| Étape | Qui | Quand | Entrée → sortie |
| --- | --- | --- | --- |
| 1. Collecte | GitHub Actions, `.github/workflows/collecte-quotidienne.yml` → `src/veille/collecte_quotidienne.py` | Chaque jour à 7 h (Paris), souvent avec du retard côté GitHub ; lancement manuel possible depuis l'onglet Actions | 16 sources (voir « Plateformes interrogées ») → `data/offres/offres_AAAA-MM-JJ.json` |
| 2. Pré-tri | `src/veille/outils.py`, règles dans `config/mots-exclus.yml`, appliqué à toutes les sources | Pendant la collecte | Retire les intitulés qui correspondent à `config/mots-exclus.yml` (vide au départ : à compléter après une semaine d'utilisation) |
| 2 bis. Filtre de titre | `collecte_quotidienne.py` + `filtrage_titres.py`, mots-clés de `config/mots-recherches.yml`, règle `titre_correspond` dans `outils.py` | Pendant la collecte, pour toutes les sources | Ne garde que les offres dont l'intitulé contient tous les mots d'au moins un mot-clé (ordre, accents, majuscules et pluriels ignorés). Les offres écartées sont consignées dans `data/etat/offres_ecartees_AAAA-MM.csv` (une ligne par offre, une seule fois) |
| 3. Dédoublonnage | `dedoublonnage.py` (`load_recent_seen_pairs`) | Pendant la collecte | Retire les offres (intitulé, recruteur) déjà collectées dans les 30 derniers jours |
| 3 bis. Dédoublonnage par lien | `dedoublonnage.py` (`load_known_urls`) | Pendant la collecte | Retire toute offre dont le lien figure dans une collecte précédente, un journal de notation ou le relevé Notion de `data/notation/references/`, sans limite de date |
| 4. Vérification en ligne | `src/veille/exclusion_offres_fermees.py` | Après la collecte | Retire les offres fermées ; garde les offres non vérifiables |
| 5. Notation | Tâche planifiée Claude « Notation veille offres emploi », consignes dans la tâche elle-même | Chaque jour à 16 h 52 (Paris) | Fichiers non notés → fiches Notion (score ≥ 40) + journal du mois `data/notation/journaux/journal_AAAA-MM.csv` |
| 6. Revue mensuelle | Tâche planifiée Claude « Revue mensuelle des offres exclues », consignes dans la tâche elle-même | Le 1er du mois, 8 h 41 | Offres exclues, faux négatifs et journaux → propositions de règles et de mots-clés à exclure (rien n'est modifié) |
| 7. Relances | Tâche planifiée Claude « Relances recherche emploi », consignes dans la tâche elle-même | Chaque lundi, 8 h 36 | Contacts et candidatures Notion → liste des relances de la semaine (rien n'est modifié) |

Référentiel des critères : l'onglet « Critères » du Claude Doc « Profil » (sections « Ce que je recherche » et « À éviter »), seul lu par les tâches. Modèle vierge à recopier : `profil/Profil - modele vierge.md`. La base Notion « Offres d'emploi » est dans la page « Recherche d'emploi » de ton espace Notion (structure : `notion/Structure des bases Notion.md`). Les textes des tâches planifiées sont dans `taches-planifiees.md`.

## Structure du dépôt

```
veille-offres-emploi/
├── README.md                       ce fichier
├── config/                         RÉGLAGES, modifiables sans programmer (YAML)
│   ├── mots-recherches.yml                mots-clés de recherche
│   ├── mots-exclus.yml                pré-tri sur l'intitulé
│   └── sources.yml                   sources actives, plafonds de volume, seuils d'alerte, fenêtres, zone JobSpy
├── src/veille/                     CODE (Python)
│   ├── collecte_quotidienne.py       chef d'orchestre : enchaîne les étapes (sources, pré-tri, filtre de titre, dédoublonnage, écriture)
│   ├── suivi_sources.py              bilan par source, date du dernier succès, règle des alertes e-mail
│   ├── dedoublonnage.py              offres déjà vues (titre + recruteur, lien), purge des vieux fichiers
│   ├── redaction_bilan.py            bilan du run : JSON, résumé GitHub Actions, sorties du workflow
│   ├── exclusion_offres_fermees.py   retire les offres fermées
│   ├── filtrage_titres.py            filtre de titre : écarte les offres sans mot-clé et tient leur journal
│   ├── outils.py                     petites fonctions génériques (règle de titre, pré-tri, clé de dédoublonnage, HTML → texte)
│   ├── lecture_config.py             lit config/ et fixe les chemins de data/
│   └── sources/                      UNE PLATEFORME PAR FICHIER
│       ├── __init__.py                 liste et ordre des sources (FETCHERS)
│       ├── _commun.py                  outils partagés par les sources
│       └── source_wttj.py, source_fashionjobs.py, …
├── data/                           DONNÉES, écrites par la collecte et la notation
│   ├── offres/                       offres_AAAA-MM-JJ[_HHMM].json, un par collecte
│   ├── etat/                         bilan_dernier_passage.json, dernier_succes_par_source.json, offres_ecartees_AAAA-MM.csv
│   └── notation/                     fichiers_notes.json, verrou.json (temporaire)
│       ├── journaux/                   journal_AAAA-MM.csv
│       └── references/                 offres_notion_connues.csv
├── tests/                          tests automatiques (aucune requête vers les sites)
├── docs/                           installation, ajout d'une source, dépannage
├── .github/workflows/              collecte-quotidienne.yml · tests.yml · capturer-pages-exemples.yml
├── requirements.txt                bibliothèques de la collecte (versions figées)
├── requirements-dev.txt            + outils de test
└── pyproject.toml                  réglages des tests et de la vérification du code
```

Règle de nommage : le nom d'un fichier de code commence par l'action qu'il réalise (`collecte_`, `suivi_`, `dedoublonnage`, `redaction_`, `exclusion_`, `filtrage_`, `lecture_`). Règle de découpage : un fichier correspond soit à une **étape lancée comme un programme** (`collecte_quotidienne.py`, `exclusion_offres_fermees.py`), soit à **une seule responsabilité** (état, dédoublonnage, rapport, journal des écartées). `outils.py` ne contient que de petites fonctions génériques, sans écriture de fichier ni requête réseau ; `sources/_commun.py` ce qui est propre aux sources.

Principe : **ce qui se règle** est dans `config/`, **ce qui s'exécute** dans `src/`, **ce que produit la veille** dans `data/`.

## Plateformes interrogées

16 sources : 2 via JobSpy dans `src/veille/sources/source_jobspy.py` (Indeed, LinkedIn), 14 dans `src/veille/sources/` (un fichier chacune, dans l'ordre de `FETCHERS`). Chacune peut être désactivée dans `config/sources.yml`.

| Clé | Plateforme | Type d'offres | Méthode | Fichier |
| --- | --- | --- | --- | --- |
| `indeed` | Indeed | Généraliste | JobSpy, un appel par mot-clé (Paris et télétravail) | `sources/source_jobspy.py` |
| `linkedin` | LinkedIn | Généraliste | JobSpy, filtre « à distance » ajouté (`f_WT=2`) | `sources/source_jobspy.py` |
| `france_travail` | France Travail | Généraliste France | API officielle, termes français (identifiants en secrets GitHub `FT_CLIENT_ID` / `FT_CLIENT_SECRET`) | `sources/source_france_travail.py` |
| `wttj` | Welcome to the Jungle | Généraliste | Algolia du site (clé publique en lecture seule) | `sources/source_wttj.py` |
| `hellowork` | Hellowork | Généraliste France | Pages HTML de recherche, termes français | `sources/source_hellowork.py` |
| `fashionjobs` | FashionJobs (offres de FashionNetwork) | Mode, luxe, beauté | Recherche plein texte par mot-clé, puis JSON-LD de chaque offre | `sources/source_fashionjobs.py` |
| `bof` | BoF Careers | Mode et beauté, international | Flux RSS par mot-clé anglais, puis JSON-LD de chaque offre | `sources/source_bof.py` |
| `fashionunited` | FashionUnited | Mode | Liste des offres à Paris (la recherche par mot-clé exige JavaScript), puis JSON-LD | `sources/source_fashionunited.py` |
| `profilculture` | ProfilCulture | Culture, art, design, communication | Catégories « Art · Design · Architecture » et « Édition · Presse · Communication », pages HTML | `sources/source_profilculture.py` |
| `sportyjob` | SportyJob | Sport et sportswear, France surtout | Flux RSS de toutes les offres, lu jusqu'au dernier passage ; filtre de titre local | `sources/source_sportyjob.py` |
| `michaelpage` | Michael Page | Cabinet de recrutement, toutes fonctions | Une page de recherche par mot-clé, puis JSON-LD (employeur réel souvent caché) | `sources/source_michaelpage.py` |
| `fashionpersonnel` | Fashion Personnel | Cabinet de recrutement mode (Londres) | Liste des offres, filtre de titre local, puis JSON-LD | `sources/source_fashionpersonnel.py` |
| `drapers` | Drapers Jobs | Mode et distribution, Royaume-Uni | Liste des offres, filtre de titre local, puis JSON-LD | `sources/source_drapers.py` |
| `ifyoucould` | If You Could Jobs | Métiers créatifs, Royaume-Uni | Offres récentes de la page d'accueil, puis JSON-LD | `sources/source_ifyoucould.py` |
| `creativeboom` | Creative Boom | Métiers créatifs, Royaume-Uni | Liste des offres, filtre sur l'adresse de l'offre, puis JSON-LD | `sources/source_creativeboom.py` |
| `dribbble` | Dribbble Jobs | Design, international, souvent en télétravail | Flux RSS, filtre de titre et de lieu, puis JSON-LD | `sources/source_dribbble.py` |

Les sources spécialisées (toutes sauf Indeed, LinkedIn, France Travail, WTTJ et Hellowork) partagent `sources/_mode.py` (lieux acceptés : France, Paris, Europe, télétravail ; un lieu connu hors de cette zone, comme Londres, est écarté sauf télétravail). Les sites britanniques (Fashion Personnel, Drapers, If You Could, Creative Boom) proposent surtout des postes à Londres : peu d'offres en sortiront ; les désactiver dans `config/sources.yml` si elles n'apportent rien après quelques semaines. Leurs pages d'exemple ne sont pas encore enregistrées : `tests/test_sources_mode.py` les teste sur des pages simulées ; lancer le workflow « Capturer les pages d'exemple » pour enregistrer les vraies.

## Fichiers de données

| Fichier | Rôle | Écrit par |
| --- | --- | --- |
| `data/offres/offres_AAAA-MM-JJ.json` | Offres collectées, une par run (un 2e run le même jour ajoute `_HHMM`) ; supprimées automatiquement après 31 jours | Collecte |
| `data/etat/bilan_dernier_passage.json` | Bilan du dernier run, par source (requêtes, erreurs, offres, sources à signaler) | Collecte |
| `data/etat/dernier_succes_par_source.json` | Dernier succès de chaque source (fenêtre de rattrapage) | Collecte |
| `data/notation/fichiers_notes.json` | Fichiers entièrement notés (`fichiers_traites`) et fichier commencé (`en_cours`) | Notation |
| `data/notation/verrou.json` | Présent seulement pendant une notation ; empêche deux notations simultanées | Notation |
| `data/notation/references/offres_notion_connues.csv` | Fiches Notion créées hors notation automatique (lien, poste, employeur), vide au départ ; avec les journaux, il remplace la lecture de Notion par la notation | Toi, si besoin |
| `data/notation/journaux/journal_AAAA-MM.csv` | Un journal par mois, une ligne par offre lue : résultat, score, motif, création Notion. Garde aussi la trace des liens après suppression des fichiers d'offres | Notation |

## En cas de problème

Voir `docs/depannage.md`. En bref :

- **Avertissement « Sources en échec » dans le résumé du run (run vert)** : une source a été entièrement en panne sur ce run, mais elle fonctionnait il y a moins de 24 h. Aucun e-mail : elle est rattrapée au run suivant grâce à `data/etat/dernier_succes_par_source.json`.
- **E-mail GitHub « Collecte quotidienne failed »** : au moins 3 sources sont en échec sur le même run, ou une source ne fonctionne plus depuis plus de 24 h (`sources_a_alerter` dans `data/etat/bilan_dernier_passage.json`). Les offres des autres sources sont enregistrées. Seuils : `config/sources.yml`, section `alertes`.
- **Bilan de notation commençant par « ÉCHEC »** : la cause suit (profil illisible, base Notion introuvable…). Le verrou est libéré ; il suffit de corriger la cause et de relancer la tâche.
- **Ne jamais lancer deux notations en même temps** (ni sous-agents) : cela crée des doublons dans Notion ; le verrou est là pour l'empêcher.

## Modifier la veille

- Mots-clés de recherche : `config/mots-recherches.yml`.
- Intitulés exclus d'office : `config/mots-exclus.yml`, liste unique pour toutes les sources (la revue mensuelle en propose de nouveaux).
- Activer ou désactiver une plateforme, seuils d'alerte, fenêtres de dédoublonnage : `config/sources.yml`.
- Plafonds de volume (résultats par recherche, pages lues, pages de détail ouvertes) : section `plafonds` de `config/sources.yml`. Quand un plafond coupe une collecte, la colonne « Plafond » du bilan (résumé du run, et `data/etat/bilan_dernier_passage.json`) l'indique. Règle : relever un plafond atteint presque chaque jour (valeur 1,5 à 2 fois le volume observé) ; laisser tel quel un plafond jamais atteint.
- Vérifier le filtre de titre : parcourir `data/etat/offres_ecartees_AAAA-MM.csv`. Si de bonnes offres s'y trouvent, ajouter le mot-clé manquant dans `config/mots-recherches.yml`.
- Critères de notation : l'onglet « Critères » du Claude Doc « Profil », pas ce dépôt.
- Déroulé de la notation : texte de la tâche planifiée « Notation veille offres emploi » (réglages de la tâche dans Claude).
- Ajouter une plateforme : `docs/ajouter-une-source.md`.

## Lancer en local

```
pip install -r requirements-dev.txt
pytest                                   # tests, sans requête vers les sites
PYTHONPATH=src python -m veille.collecte_quotidienne # collecte complète (1 h 30 à 2 h 30 avec ~130 mots-clés, depuis la racine du dépôt)
```
