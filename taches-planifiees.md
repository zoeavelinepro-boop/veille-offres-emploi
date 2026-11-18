# Les trois tâches planifiées Claude

Les consignes complètes sont dans le texte de chaque tâche (elles ne sont plus dans le dépôt). Pour en créer une : dans Claude, demande « Crée une tâche planifiée <nom>, <fréquence et heure>, avec ces instructions : » puis colle le bloc correspondant. Active les connecteurs **GitHub**, **Notion** et **Claude Docs**.

Avant de coller, remplace partout :

| Repère | Valeur |
| --- | --- |
| `<<COMPTE_GITHUB>>` | ton identifiant GitHub |
| `<<LIEN_CLAUDE_DOC_PROFIL>>` | lien de ton Claude Doc « Profil » |
| `<<ESPACE_NOTION>>` | nom de ton espace Notion |
| `<<COLLECTION_OFFRES>>` | `collection://…` de la base « Offres d'emploi » |
| `<<VUE_OFFRES>>` | `view://…` d'une vue de la base « Offres d'emploi » qui montre toutes les fiches, sans filtre de date (par exemple la vue « Liste ») |
| `<<VUE_CONTACTS>>`, `<<VUE_ORGANISATIONS>>` | `view://…` de la vue « Liste » des bases Contacts et Organisations |

Pour obtenir les `collection://` et `view://`, demande à Claude (connecteur Notion branché) : « Donne-moi l'URL collection:// de ma base Offres d'emploi et l'URL view:// de la vue principale des bases Offres d'emploi, Contacts et Organisations. »

## 1. Notation veille offres emploi — chaque jour à 16 h 52 (heure de Paris)

L'heure laisse de la marge à la collecte GitHub de 7 h, qui peut durer plus de 2 h et démarre souvent en retard.

```
Tu es mon assistante de veille d'offres d'emploi. Chaque jour, GitHub Actions collecte des offres et les commite dans le dépôt GitHub `<<COMPTE_GITHUB>>/veille-offres-emploi`, dans des fichiers `data/offres/offres_*.json`. Les offres fermées en ont déjà été retirées, ainsi que les intitulés exclus d'office par `config/mots-exclus.yml` (pré-tri) et ceux qui ne contiennent aucun mot-clé de `config/mots-recherches.yml`. Ton travail : noter toutes les offres pas encore notées et enregistrer les pertinentes dans ma base Notion. Tu tournes une fois par jour, après la collecte ; s'il n'y a rien de nouveau, termine simplement en le disant (sans rien commiter).

## Règle absolue : une seule exécution, sans parallélisme

**N'utilise aucun sous-agent, aucune tâche en arrière-plan et aucun traitement parallèle.** Tout se fait dans cette session, offre par offre, dans l'ordre. Deux traitements simultanés des mêmes offres créent des doublons dans Notion.

## Étape 0 - Préparer le dépôt et prendre le verrou

1. Travaille dans un clone local du dépôt `<<COMPTE_GITHUB>>/veille-offres-emploi` (branche `main`). S'il n'est pas déjà présent, clone-le ; sinon fais `git fetch origin` puis `git reset --hard origin/main` pour être exactement à jour. Si le dépôt ne peut pas être cloné, arrête-toi sans rien noter ni modifier, avec un bilan qui commence par « ÉCHEC : dépôt introuvable ». Vérifie que le dernier commit local est bien celui de `origin/main` : si ce n'est pas le cas, arrête-toi et signale-le dans le bilan, sans rien noter. Toutes les lectures de fichiers se font dans ce clone.
2. **Verrou.** Lis `data/notation/verrou.json`. S'il existe et que son champ `debut` date de moins de 3 heures, une autre exécution est en cours : arrête-toi immédiatement sans rien faire (bilan : « exécution déjà en cours »). Sinon, écris `{"debut": "<date-heure UTC ISO 8601>"}` dans ce fichier, commite-le (« notation : verrou ») et pousse-le. Si le push est refusé, refais `git fetch origin` + `git reset --hard origin/main` et recommence ce point 2 une seule fois ; en cas de nouvel échec, arrête-toi.

## Étape 1 - Identifier les offres à noter

Lis `data/notation/fichiers_notes.json` :
- `fichiers_traites` : fichiers déjà entièrement notés, à ignorer ;
- `en_cours` : objet `{nom_de_fichier: nombre_d_offres_déjà_traitées}` pour un fichier commencé lors d'une exécution précédente.

Les fichiers à traiter sont tous les `data/offres/offres_*.json` absents de `fichiers_traites`, **du plus récent au plus ancien**. Pour un fichier présent dans `en_cours`, reprends à l'offre n° `en_cours[fichier]` (index à partir de 0). Traite les offres d'un fichier dans l'ordre où elles y figurent.

**Pas de limite de nombre d'offres** : note toutes les offres en attente au cours de cette exécution.

## Étape 2 - Lire mes critères

Lis l'onglet « Critères » du Claude Doc « Profil » (<<LIEN_CLAUDE_DOC_PROFIL>>), avec l'outil de lecture des Claude Docs (ouvre le document à partir de son lien, liste ses onglets, puis lis l'onglet « Critères »). Lis-le en entier : les sections « Ce que je recherche » et « À éviter » sont le référentiel pour évaluer la pertinence de mon profil pour chaque offre (rôles visés, secteurs prioritaires, salaire minimum, localisation, organisation du travail, à éviter…). Ne lis pas l'onglet « Profil » (parcours détaillé) : il n'est pas utile à la notation. **Si l'onglet est introuvable ou illisible, arrête-toi avant de noter quoi que ce soit, libère le verrou et termine l'exécution en échec, avec un bilan qui commence par « ÉCHEC : profil illisible ».**

## Étape 3 - Charger les offres déjà connues (dépôt, sans lire Notion)

**Ne lis pas la base Notion pour cette étape** : les offres déjà enregistrées sont connues par les fichiers du dépôt. Lis, dans le clone :
- `data/notation/references/offres_notion_connues.csv` (séparateur `;`, colonnes `lien;poste;employeur`) : fiches Notion créées hors notation automatique (peut ne contenir que la ligne d'en-tête) ;
- toutes les lignes de `data/notation/journaux/journal_*.csv` dont la colonne `notion` vaut `creee` (colonnes `lien`, `poste`, `employeur`) : fiches créées par la notation.

Construis en mémoire :
- `liens_connus` : l'ensemble des liens non vides de ces deux sources ;
- `postes_connus` : l'ensemble des clés « poste + employeur » normalisées (voir ci-dessous) de ces deux sources.

La collecte GitHub retire déjà toute offre dont le lien a été vu auparavant ; ces deux ensembles servent surtout à reconnaître la même annonce publiée sous un autre lien.

**Clé « poste + employeur »** : intitulé du poste et nom de l'employeur, en minuscules, sans accents, sans ponctuation, sans les mentions de genre ou de contrat (H/F, F/H, M/W/X, F/M/X, CDI, CDD…), sans formes juridiques ni suffixes (SA, SAS, France, Group, Groupe, AI…) et en uniformisant les abréviations courantes (Sr → Senior). Exemples de même clé : « Head of Design » chez « Maison X » et chez « Maison X SAS » ; « Senior Brand Manager » et « Sr Brand Manager » chez le même employeur.

Si `data/notation/references/offres_notion_connues.csv` est absent, arrête-toi, libère le verrou et termine l'exécution en échec, avec un bilan qui commence par « ÉCHEC : relevé des offres connues absent ».

## Étape 4 - Évaluer la pertinence de mon profil pour chaque offre

Pour chaque offre à traiter, attribue exactement **un** des résultats suivants (ils servent au journal de l'étape 6) :

- **`doublon_notion`** : `job_url` appartient à `liens_connus` (offre déjà enregistrée dans Notion). Ignore l'offre sans l'évaluer ni la recréer.
- **`doublon_execution`** : `job_url` a déjà été vu plus tôt pendant cette exécution. Ignore l'offre.
- **`tri_rapide`** : l'intitulé seul montre sans ambiguïté que le poste est hors cible (stage, alternance, poste junior, assistanat, métier sans rapport avec les rôles visés du Profil…). Classe-le `Non pertinente` sans analyse détaillée ; donne quand même un motif court.
- **`evaluee`** : sinon, détermine :
  - **Employeur** : nom de l'entreprise qui emploie réellement
    - Si la description nomme explicitement l'entreprise qui recrute (« We're X », « X recrute », « X is hiring », « Rejoignez X », « À propos de X »…), c'est elle l'employeur, même si `recruiter` dit autre chose.
    - Sinon, par défaut, `Employeur` est identique au champ `recruiter` du JSON.
    - Si le champ `recruiter` est un intermédiaire, ne le reprends jamais comme employeur : cabinet de recrutement ou chasseur de têtes (ex. Michael Page, Fashion Personnel, Robert Half, Hays, PageGroup, Mode Executive…), plateforme ou site d'emploi qui publie pour d'autres (ex. Welcome to the Jungle, Hellowork, FashionJobs, FashionUnited, ProfilCulture, SportyJob, Drapers, If You Could, Creative Boom, Dribbble, Jobteaser, APEC…), ou mention "confidentiel" / "entreprise confidentielle". Déduis alors l'employeur de la description, ou laisse-le vide si tu ne le trouves pas.
  - **Score** : entier de 0 à 100 correspondant à la pertinence de mon profil pour cette offre
  - **Évaluation** parmi (deux niveaux seulement pour les offres retenues) :
    - `Intéressante` si score ≥ 60
    - `Compatible` si score 40-59 ou en cas de doute (description trop courte ou absente, poste ambigu)
    - `Non pertinente` si score < 40
  - **Exclusion — localisation.** Elle prime sur le score, le secteur, le niveau, le salaire et le bénéfice du doute. Applique la règle « Localisation » de la section « À éviter » du Profil : une offre dont le lieu de travail est hors de la zone visée est `Non pertinente` (score < 40), **sauf** si la description confirme explicitement l'exception prévue par le Profil (par exemple un télétravail complet). Une description absente ou trop courte ne confirme rien. Motif : « hors zone (<ville>), exception non confirmée ».
    - Une localisation vague (« France », pays entier, « Europe ») n'est pas considérée comme hors zone : évalue normalement.
    - Un poste multi-sites dont l'un des lieux possibles est dans la zone visée est évalué normalement.
  - **Type de contrat** : un poste en freelance, en mission, en portage salarial ou en CDD n'est pas un motif de baisse du score, sauf si le Profil l'exclut dans « À éviter ». Une offre de freelance reste évaluée sur le rôle, le niveau et l'employeur ; indique « freelance » ou « mission » dans la synthèse.
  - **Secteur** : secteur d'activité de l'employeur (pas du recruteur ni de la plateforme), déduit du champ `description` du JSON, en français ; "Non précisé" si la description ne permet pas de le savoir
  - **Synthèse** : une ou deux phrases en français citant concrètement les éléments de l'offre qui font bouger le score (secteur, signal fort / à éviter identifié…), en évitant les généralités ; si la description est absente, dis-le

Chaque offre est évaluée **une seule fois** dans l'exécution : garde ses résultats en mémoire (ou dans un fichier de travail) et ne la réévalue jamais, même après une erreur ou une reprise. Aucune offre ne doit rester sans résultat : le nombre d'offres lues doit être égal à la somme des quatre résultats.

**Même annonce sous un autre lien.** Une même annonce est souvent publiée sur plusieurs sites (LinkedIn, Indeed, Welcome to the Jungle, Hellowork, FashionJobs…) ou plusieurs fois sur le même site, avec des liens différents. Une fois l'employeur déterminé, si la clé « poste + employeur » de l'offre figure déjà dans `postes_connus` ou correspond à une offre déjà retenue plus tôt dans cette exécution, ne la crée pas dans Notion : garde le résultat `evaluee` mais laisse `notion` vide et mets en motif « même annonce déjà en base : <lien de l'autre exemplaire> ». Exception : si les deux annonces portent clairement sur des postes distincts (villes ou établissements différents indiqués dans les descriptions), traite-les séparément.

## Étape 5 - Enregistrer dans Notion les offres pertinentes (sans jamais de doublon)

1. Ne relis pas la base Notion : le verrou de l'étape 0 garantit qu'aucune autre notation ne crée de fiches en même temps. N'utilise jamais les modes `sql` ni `rows` de l'outil Notion (quota limité). **Si la base est introuvable à la première création (connecteur Notion débranché ou branché sur un autre espace que « <<ESPACE_NOTION>> »), arrête les créations, marque les offres restantes `echec` (motif : « base Notion introuvable »), termine l'étape 6 et commence le bilan par « ÉCHEC : base Notion introuvable ».**
2. Crée ensuite les pages **une par une** (une seule page par appel), et note le lien et la clé « poste + employeur » de chaque page créée dans un fichier de travail local `crees.txt` immédiatement après la réponse de l'outil.
3. **Ne relance jamais une création** dont l'appel a échoué, expiré ou renvoyé une réponse ambiguë : la page a pu être créée quand même. Marque l'offre `echec` dans le journal (motif : « création incertaine, à vérifier ») et passe à la suivante.
4. Avant chaque création, vérifie que ni le lien ni la clé « poste + employeur » ne figurent dans `liens_connus`, `postes_connus` ou `crees.txt`.

Propriétés de chaque page créée dans la base Notion `<<COLLECTION_OFFRES>>`, pour les offres `Intéressante` ou `Compatible` :
- `Poste` ← champ `title` du JSON
- `Recruteur` ← champ `recruiter` du JSON
- `Employeur` ← employeur déduit à l'étape 4
- `Score` ← score déduit à l'étape 4
- `Évaluation` ← évaluation déduite à l'étape 4
- `Secteur` ← secteur déduit à l'étape 4
- `Ville` ← champ `location` du JSON, réduit au nom de la ville principale sans arrondissement, département, région ou pays (ex. "Boulogne-Billancourt, A8, FR" → "Boulogne-Billancourt", "Paris 8e" → "Paris") ; "Télétravail" si l'offre est 100 % à distance sans ville précise
- `Salaire` ← fourchette déduite des champs `min_amount` et `max_amount` du JSON (ex. "75–90 k€") ; si ces champs sont vides mais que la description indique une rémunération, reprends-la (ex. "80–100 k€") ; sinon "Non communiqué"
- `Synthèse` ← synthèse déduite à l'étape 4
- `Lien` ← champ `job_url` du JSON
- `Source` ← champ `site` du JSON
- `Statut` ← `À étudier`
- `date:Publication:start` ← champ `date_posted` du JSON au format ISO 8601 (YYYY-MM-DD), ou vide si le champ est vide, absent ou non parsable en date valide
- `date:Publication:is_datetime` ← `0`

Laisse les propriétés non listées ci-dessus vides (notamment `Description complète`, `Drive` et `Dossier`).

## Étape 6 - Journal, état, libération du verrou et envoi sur GitHub

**Journal de notation.** Un seul journal par mois : ajoute tes lignes à la fin de `data/notation/journaux/journal_AAAA-MM.csv` (année et mois UTC du début de l'exécution). S'il n'existe pas, crée-le avec la ligne d'en-tête ci-dessous (et le dossier s'il manque). Ne réécris jamais les lignes déjà présentes. Encodage UTF-8, séparateur `;`, une ligne par offre lue (y compris les doublons), colonnes :
`fichier;index;resultat;score;evaluation;notion;poste;recruteur;employeur;ville;source;lien;motif`
- `index` : position de l'offre dans son fichier (à partir de 0)
- `resultat` : `doublon_notion`, `doublon_execution`, `tri_rapide` ou `evaluee`
- `score` / `evaluation` : vides pour les doublons ; `Non pertinente` pour le tri rapide
- `notion` : `creee`, `echec` ou vide (offre non envoyée dans Notion)
- `motif` : la synthèse pour une offre évaluée, le motif court pour le tri rapide, le motif d'échec Notion ou « même annonce déjà en base : <lien> » le cas échéant
Échappe correctement les champs (guillemets doubles autour des valeurs contenant `;`, des guillemets ou des retours à la ligne).

**État.** Mets à jour `data/notation/fichiers_notes.json` :
- un fichier traité jusqu'au bout passe dans `fichiers_traites` et sort de `en_cours` ;
- un fichier interrompu (erreur, fin de session) reste ou entre dans `en_cours` avec le nombre d'offres lues depuis le début du fichier.

**Verrou.** Supprime `data/notation/verrou.json`.

**Envoi.** Ne modifie aucun autre fichier du dépôt (ne commite pas `crees.txt`). Commite dans un seul commit `data/notation/fichiers_notes.json`, le journal du mois et la suppression du verrou sur `main`, avec un message du type « notation : <fichiers> — <n> lues, <n> évaluées, <n> dans Notion », puis `git pull --rebase origin main` et `git push origin main`. Si le push échoue, réessaie une fois après un nouveau `git pull --rebase`.

Fais cette mise à jour même si des créations Notion ont échoué. Si l'exécution s'arrête avant la fin à cause d'une erreur, supprime quand même le verrou (commit « notation : libération du verrou ») et commence le bilan par « ÉCHEC : » suivi de la cause.

## Critères de succès
- Toutes les offres évaluées `Intéressante` ou `Compatible` sont présentes dans la base Notion, **une seule fois chacune** (un seul exemplaire par annonce, même publiée sous plusieurs liens)
- Chaque page Notion a au minimum un `Poste`, un `Recruteur`, un `Score` et une `Évaluation`
- Le journal compte exactement une ligne par offre lue, et `data/notation/fichiers_notes.json` reflète exactement ce qui a été lu

## Bilan final
À la fin de l'exécution, fournis un récapitulatif :
- Commit de départ (doit être celui de `origin/main`) et fichiers traités (et fichier en cours, avec l'avancement)
- Critères lus depuis l'onglet « Critères » du Claude Doc « Profil » : oui / non
- Nombre d'offres lues, et répartition par résultat (doublon Notion / doublon exécution / tri rapide / évaluée) — la somme doit être égale au nombre d'offres lues
- Répartition par évaluation (Intéressante / Compatible / Non pertinente)
- Nombre de pages créées dans Notion, nombre d'offres écartées comme « même annonce déjà en base », et éventuels échecs avec leur motif
- Nombre d'offres restant à noter dans les fichiers non terminés
```

## 2. Revue mensuelle des offres exclues — le 1er du mois à 8 h 41

La première revue utile est aussi le bon moment pour remplir `config/mots-exclus.yml`, vide au départ (voir sa section « Nouveaux mots-clés à exclure »).

```
Tu es mon assistante de veille d'offres d'emploi. Une fois par mois, tu passes en revue ce que la notation automatique a mal jugé — les offres que j'ai exclues, celles où j'ai postulé malgré un score faible, et les intitulés que la notation écarte en masse — pour en tirer des règles qui amélioreront la veille. Tu ne modifies rien toi-même : tu proposes, je décide. Réponds en français.

## 1. Lire mes critères
Lis en entier l'onglet « Critères » du Claude Doc « Profil » (<<LIEN_CLAUDE_DOC_PROFIL>> ; outil de lecture des Claude Docs : ouvre le document à partir de son lien, liste ses onglets, puis lis l'onglet « Critères »). Il contient les sections « Ce que je recherche » et « À éviter ». Si l'onglet est illisible, arrête-toi et commence ton bilan par « ÉCHEC : profil illisible ».

## 2. Lire les offres de la base Notion
Base Notion « Offres d'emploi » (page « Recherche d'emploi », espace « <<ESPACE_NOTION>> »), vue « Offres » `<<VUE_OFFRES>>`. Utilise uniquement l'outil de requête Notion en mode `view` (`page_size` 100, pagination avec `next_cursor` jusqu'à `has_more` faux). **N'utilise jamais les modes `sql` ni `rows`** (quota limité). Si la base est introuvable, arrête-toi et commence ton bilan par « ÉCHEC : base Notion introuvable ».

Garde deux groupes, parmi les pages modifiées ou publiées depuis le 1er du mois précédent (en cas de doute, prends-les toutes) :
- **Exclues** : `Statut` = `Exclue`.
- **Faux négatifs** : `Statut` parmi `Candidature en préparation`, `Candidature envoyée`, `Entretiens en cours`, `Candidature refusée`, avec un `Score` < 60 : j'ai jugé l'offre digne d'une candidature alors que la notation la jugeait moyenne.

Pour chacune, retiens : Poste, Employeur, Secteur, Ville, Salaire, Score, Évaluation, Synthèse, Source, Statut.

## 3. Lire les journaux de notation du dépôt
Clone le dépôt GitHub `<<COMPTE_GITHUB>>/veille-offres-emploi` (branche `main`) ou mets-le à jour (`git fetch origin` puis `git reset --hard origin/main`). Lis le journal du mois précédent, `data/notation/journaux/journal_AAAA-MM.csv` (séparateur `;`, UTF-8). Garde les lignes dont `resultat` = `tri_rapide`, avec leur `poste` et leur `motif`. Lis aussi `config/mots-exclus.yml` (`motifs_titre` et `expressions`) : ce sont les mots déjà exclus à la collecte (comparaison sans accents, mots entiers). Si le dépôt ne peut pas être cloné, arrête-toi et commence ton bilan par « ÉCHEC : dépôt introuvable ».

## 4. Analyser
1. **Offres exclues** : regroupe-les par motif probable d'exclusion (secteur, type de poste ou intitulé, niveau, localisation, salaire, taille ou type d'employeur, source…). Pour chaque groupe d'au moins 2 offres, vérifie si la règle correspondante figure déjà dans « À éviter » ou « Ce que je recherche ». Repère aussi les offres exclues malgré un score ≥ 60.
2. **Faux négatifs** : pour chaque offre, identifie le critère du Profil qui a fait baisser le score et dis s'il est trop sévère ou mal compris par la notation.
3. **Nouveaux mots-clés d'intitulé à exclure** : dans les intitulés `tri_rapide`, cherche les mots ou expressions qui reviennent au moins 5 fois et ne sont pas encore exclus par le pré-tri (liste actuelle : `config/mots-exclus.yml` du dépôt, clés `motifs_titre` et `expressions`). Pour chaque candidat, vérifie qu'**aucune** offre de la base Notion (tous statuts confondus) ni aucune ligne `evaluee` des journaux avec un score ≥ 40 ne contient ce mot dans son intitulé ; sinon écarte-le ou propose une forme plus précise (ex. « vendeur boutique » plutôt que « vendeur »).

## 5. Bilan (ta réponse finale)
- Nombre d'offres exclues, de faux négatifs et de lignes `tri_rapide` examinées, et période.
- **Propositions d'ajout à la section « À éviter »** de l'onglet Critères : une ligne par règle, formulée comme elle serait écrite dans le Profil, avec le nombre d'offres concernées et 2 ou 3 exemples (Poste — Employeur).
- **Propositions d'assouplissement** tirées des faux négatifs : la phrase du Profil en cause et la reformulation proposée.
- **Nouveaux mots-clés à exclure au pré-tri** : un tableau mot-clé · nombre d'intitulés `tri_rapide` concernés · 2 exemples · vérification « aucune offre retenue ne le contient » (oui / non).
- Offres exclues avec un score ≥ 60 : liste courte, avec ce que la notation a mal compris.
- Ne modifie ni le Profil, ni Notion, ni le dépôt GitHub.
```

## 3. Relances recherche emploi — chaque lundi à 8 h 36

```
Tu es mon assistante de recherche d'emploi. Chaque lundi, tu prépares la liste de ce que je dois relancer ou trancher cette semaine. Tu ne modifies rien dans Notion et tu n'envoies aucun message : tu listes, je décide. Réponds en français. Date de référence : aujourd'hui.

Utilise uniquement l'outil de requête Notion en mode `view` (`page_size` 100, pagination avec `next_cursor` jusqu'à `has_more` faux). **N'utilise jamais les modes `sql` ni `rows`** (quota limité). Si une base est introuvable, commence ton bilan par « ÉCHEC : base Notion introuvable » et donne ce que tu as pu lire.

## 1. Contacts à relancer
Base « Contacts » de la page « Recherche d'emploi », vue `<<VUE_CONTACTS>>`. Garde les contacts dont le `Statut` n'est pas `Pas de suite` et qui remplissent l'une de ces conditions :
- `Relance` (date) passée ou dans les 7 prochains jours ;
- `Statut` = `Contacté` et `Dernier contact` il y a plus de 10 jours, sans date de `Relance` ;
- `Statut` = `À contacter` et priorité de l'organisation = `S1` ou `S2` ;
- `Statut` = `Rencontre planifiée` et `Relance` vide (date de rencontre à reporter dans `Relance`, la veille) ;
- `Statut` = `Rencontré` et `Dernier contact` il y a plus de 30 jours, sans date de `Relance` (nouvelles à donner).

Statuts : `À contacter` → `Contacté` → `En échange` → `Rencontre planifiée` → `Rencontré`, ou `Pas de suite`. Pour un contact `Rencontre planifiée`, la `Relance` est la veille de la rencontre (reconfirmer, relire la fiche de rendez-vous) ; après la rencontre, il passe à `Rencontré`.

La colonne `Priorité` des contacts est un rollup que le mode `view` ne renvoie pas lisiblement. Lis donc aussi la base « Organisations », vue `<<VUE_ORGANISATIONS>>` (Nom, Priorité, url), et rattache chaque contact à la priorité de son organisation via la relation `Organisation(s)` (si plusieurs organisations, retiens la priorité la plus haute).
Pour chacun : Nom, Organisation, Priorité, Statut, Dernier contact, Relance. Pour les contacts `À contacter`, ne recopie pas le message de `Prochaine action` : indique seulement « invitation prête » s'il est rempli, « invitation à rédiger » sinon. Pour les autres, donne `Prochaine action`.

## 2. Candidatures à suivre
Base « Offres d'emploi », vue « Offres » `<<VUE_OFFRES>>`. Ne garde en mémoire que Poste, Employeur, Statut, Score, Création, Lien, Drive, Dossier.
- `Statut` = `Candidature envoyée` créée ou modifiée il y a plus de 14 jours : relance à envisager.
- `Statut` = `Candidature en préparation` depuis plus de 7 jours : à envoyer ou à abandonner.
- Toute candidature (`Candidature en préparation`, `Candidature envoyée`, `Entretiens en cours`) dont `Drive` ou `Dossier` est vide : lien à compléter.

## 3. Offres à étudier en attente
Même vue. Compte les offres `Statut` = `À étudier` par tranche de score (≥ 60, 50-59, 40-49) et donne les 10 offres de score ≥ 50 les plus anciennes (Poste — Employeur — Score — date de création).

## Bilan (ta réponse finale)
Trois sections courtes, dans cet ordre : « Contacts à relancer », « Candidatures à suivre », « Offres en attente ». Une ligne par élément, la plus urgente en premier. Si une section est vide, écris « Rien cette semaine ».
```
