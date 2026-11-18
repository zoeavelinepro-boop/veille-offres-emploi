# Dépannage

## Une source est en panne

1. Ouvrir le résumé du run dans l'onglet Actions de GitHub : un tableau donne, par source, les requêtes, les erreurs et l'état. Le détail est aussi dans `data/etat/bilan_dernier_passage.json` (`note` de chaque source).
2. Une panne **isolée et récente** n'envoie pas d'e-mail : la source est rattrapée au run suivant (sa date de dernier succès n'avance pas).
3. Une panne qui **dure plus de 24 h**, ou **3 sources en panne en même temps**, fait échouer le run (e-mail GitHub).

Causes fréquentes :

| Message | Cause probable | Action |
| --- | --- | --- |
| `HTTPError 500` | Le site est momentanément en panne | Attendre le run suivant |
| `élément … introuvable` | Le site a changé sa page | Ouvrir la page dans un navigateur, comparer avec le code de `src/veille/sources/<source>.py`, corriger la lecture |
| `403` / `429` | Le site bloque le robot | Allonger `PAUSE`, réduire les requêtes ; sinon désactiver la source dans `config/sources.yml` |
| 0 offre sans erreur (Indeed, LinkedIn) | Blocage anti-robot silencieux | Avertissement dans le résumé ; relancer plus tard |


## Désactiver une source en attendant

Dans `config/sources.yml`, mettre `actif: false` pour la source. Elle n'est plus appelée ni comptée dans le bilan.

## La notation

- **Bilan commençant par « ÉCHEC »** : la cause suit (profil illisible, base Notion introuvable…). Le verrou est libéré ; corriger la cause et relancer la tâche.
- **« exécution déjà en cours »** : si aucune notation ne tourne et que `data/notation/verrou.json` a plus de 3 heures, il est ignoré automatiquement ; sinon, le supprimer à la main.
- **Fichier noté à moitié** : il figure dans `en_cours` de `data/notation/fichiers_notes.json` avec le nombre d'offres déjà lues ; la notation suivante reprend à cet endroit.
- **Ne jamais lancer deux notations en même temps.**

## Tester une modification

`pytest` en local ou le workflow « Tests » sur GitHub (déclenché à chaque modification de `src/`, `config/` ou `tests/`). Puis lancer une collecte manuelle depuis l'onglet Actions pour vérifier en réel.
