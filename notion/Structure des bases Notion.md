# Structure des bases Notion

Trois bases dans une page « Recherche d'emploi » de ton espace Notion. Les noms des bases, des propriétés et des options doivent être **exactement** ceux-ci (accents et majuscules compris) : les consignes de `prompts/` et les skills les utilisent tels quels.

Le plus simple : connecte Notion à Claude, puis colle ce fichier dans une conversation avec la demande « Crée dans mon Notion une page "Recherche d'emploi" contenant ces trois bases, avec exactement ces propriétés et ces options ».

## Base « Offres d'emploi »

| Propriété | Type | Options / remarque |
| --- | --- | --- |
| Poste | Titre | |
| Recruteur | Texte | |
| Employeur | Texte | |
| Score | Nombre | entier, affiché en barre sur 100 |
| Évaluation | Sélection | `Intéressante`, `Compatible` |
| Statut | Statut | À faire : `À étudier` (par défaut) · En cours : `Candidature en préparation`, `Candidature envoyée`, `Entretiens en cours` · Terminé : `Candidature refusée`, `Candidature manquée`, `Exclue` |
| Secteur | Texte | |
| Ville | Texte | |
| Salaire | Texte | |
| Synthèse | Texte | |
| Description complète | Texte | |
| Lien | URL | |
| Source | Texte | |
| Publication | Date | |
| Création | Date de création | |
| Drive | URL | lien du dossier de candidature sur Google Drive |
| Dossier | URL | lien du dossier de candidature (Claude Doc) |
| Organisation | Relation | vers « Organisations » (propriété en retour : `Offre(s)`) |

Vue principale : « Offres » (tableau, toutes les fiches).

## Base « Organisations »

| Propriété | Type | Options / remarque |
| --- | --- | --- |
| Nom | Titre | |
| Type | Sélection | `Employeur`, `Cabinet de recrutement`, `Plateforme` |
| Priorité | Sélection | `S1`, `S2`, `Plus tard` |
| Secteur | Sélection multiple | à définir selon tes secteurs cibles (ex. un secteur prioritaire, « Impact », « Généraliste ») |
| Activité | Texte | |
| Localisation(s) | Texte | |
| Site | URL | |
| Contact(s) | Relation | vers « Contacts » (propriété en retour : `Organisation(s)`) |
| Offre(s) | Relation | vers « Offres d'emploi » |

## Base « Contacts »

| Propriété | Type | Options / remarque |
| --- | --- | --- |
| Nom | Titre | |
| Organisation(s) | Relation | vers « Organisations » |
| Priorité | Rollup | `Organisation(s)` → `Priorité` |
| Type | Rollup | `Organisation(s)` → `Type` |
| Statut | Sélection | `À contacter`, `Contacté`, `En échange`, `Rencontre planifiée`, `Rencontré`, `Pas de suite` |
| Dernier contact | Date | |
| Relance | Date | |
| Prochaine action | Texte | |
| Profil | Texte | |
| Email | E-mail | |
| LinkedIn | URL | |

Une fois les bases créées, demande à Claude les URL `collection://` (base Offres d'emploi) et `view://` (vue principale de chaque base) pour remplir les repères `<<…>>` des tâches planifiées (voir `taches-planifiees.md`).
