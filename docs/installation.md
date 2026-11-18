# Installer la veille de zéro

Ce que la veille demande, dans l'ordre. Le guide d'installation pas à pas (Profil, base Notion, skills, tâches planifiées) accompagne ce dépôt ; ce fichier en rappelle l'essentiel.

## 1. Le dépôt GitHub

1. Copier ce dépôt dans un compte GitHub (privé : il contient les offres collectées).
2. Dans *Settings → Actions → General*, autoriser les workflows et donner aux workflows le droit d'écrire dans le dépôt (le workflow enregistre les données).
3. **Secrets** (*Settings → Secrets and variables → Actions*), facultatifs :
   - `FT_CLIENT_ID` et `FT_CLIENT_SECRET` : identifiants de l'API France Travail (https://francetravail.io). Sans eux, la source France Travail est simplement ignorée.
4. Adapter `config/` : `mots-recherches.yml` (mots-clés), `mots-exclus.yml` (pré-tri), `sources.yml` (sources actives, zone de recherche `zone_paris`, plafonds de volume).
5. Lancer le workflow « Collecte quotidienne » depuis l'onglet Actions : il doit produire `data/offres/offres_AAAA-MM-JJ.json`. Les premiers passages créent `data/etat/`.

## 2. La notation par Claude

La notation n'est pas dans GitHub : ce sont des tâches planifiées Claude dont le texte contient les consignes.

1. **Un Profil** : un document décrivant la personne et ses critères, avec un onglet « Critères » (sections « Ce que je recherche » et « À éviter »). Adapter la référence du document dans le texte de la tâche de notation.
2. **Une base Notion** « Offres d'emploi » (propriétés énumérées à l'étape 5 de la tâche de notation). Adapter ses références dans le texte de la tâche.
3. **Le relevé initial** : `data/notation/references/offres_notion_connues.csv` (colonnes `lien;poste;employeur`, séparateur `;`), avec les fiches déjà présentes dans Notion ; vide si la base est neuve. et dans le texte de la tâche de notation si la date change.
4. **Créer les trois tâches planifiées Claude** (textes prêts dans `taches-planifiees.md`) (notation, revue mensuelle des exclues, relances). Le texte de chaque tâche contient ses consignes complètes. Les tâches de notation et de revue clonent d'abord le dépôt `main` (ou le mettent à jour par `git fetch origin` puis `git reset --hard origin/main`) ; celle des relances ne lit que Notion. Horaires actuels : notation chaque jour à 16 h 52, revue mensuelle le 1er à 8 h 41, relances le lundi à 8 h 36 (heure de Paris). La notation doit avoir lieu après la collecte de 7 h (GitHub la retarde parfois de plusieurs heures).
5. Connecteurs nécessaires aux tâches : Notion (notation, revue, relances), Claude Docs (lecture du Profil), et le dépôt GitHub.

## 3. Vérifier

- `pytest` passe (workflow « Tests »).
- Une collecte manuelle réussit et le résumé du run liste les 16 sources.
- La notation, lancée à la main une première fois, crée `data/notation/journaux/journal_AAAA-MM.csv` et `data/notation/fichiers_notes.json`.
