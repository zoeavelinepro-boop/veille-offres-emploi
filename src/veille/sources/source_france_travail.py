"""France Travail (API officielle, OAuth2).

Une fonction `fetch_*` par source ; voir veille/sources/__init__.py pour l'ordre d'appel."""

from __future__ import annotations

import json
import os

import requests

from veille.lecture_config import plafond
from veille.outils import MAX_DESC_CHARS, dedup_key, now_utc

RESULTATS_PAR_RECHERCHE = plafond("france_travail", "resultats_par_recherche", 50)


FT_CLIENT_ID = os.environ.get("FT_CLIENT_ID", "")
FT_CLIENT_SECRET = os.environ.get("FT_CLIENT_SECRET", "")

# =============================================================================
# FRANCE TRAVAIL API
# =============================================================================
# Documentation officielle : https://francetravail.io/data/api/offres-emploi
# Authentification OAuth2 (client_credentials) → token Bearer valable 25 min.
# On envoie une requête de recherche par mot-clé "ft" de SEARCHES.

def _format_list_entries(
    items: list[dict] | None,
    label: str,
    keys: tuple[str, ...],
    with_exigence: bool = True,
) -> list[str]:
  
    """Formate une liste de dicts en lignes `label : key1 / key2 / …`.
    Utilisé pour aplatir les sous-listes de l'API France Travail (formations,
    compétences, langues, qualités professionnelles) en texte lisible.
    - `keys` : champs à extraire dans l'ordre.
    - `with_exigence` : si True, on ajoute `exigence : <val>` au bout
      lorsque le dict contient une clé "exigence" (ex: "Souhaité"/"Exigé")."""
  
    out: list[str] = []
    for item in items or []:
        bits = [item.get(k) for k in keys]
        if with_exigence and (exigence := item.get("exigence")):
            bits.append(f"exigence : {exigence}")
        # Filtrer les valeurs None/"" pour ne pas avoir de " /  / " disgracieux.
        bits = [b for b in bits if b]
        if bits:
            out.append(f"{label} : " + " / ".join(bits))
    return out

def build_description(offer: dict) -> str:
  
    """Aplatit une offre France Travail en une description texte enrichie.
    Le but est de fournir à Claude
    un maximum de contexte structuré : description, entreprise, expérience,
    formations, langues, compétences, etc.
    Chaque champ est précédé d'un libellé en français pour rester lisible.
    Les blocs vides sont automatiquement ignorés via le helper local `add`."""
  
    parts: list[str] = []

    def add(label: str, value) -> None:
        """Ajoute un bloc 'label : valeur' si la valeur est non vide."""
        if value:
            parts.append(f"{label} : {value}")

    # Champs principaux (chaînes simples).
    add("Description", offer.get("description"))
    add("Entreprise", (offer.get("entreprise") or {}).get("description"))
    add("Expérience", offer.get("experienceLibelle"))
    add("Commentaire expérience", offer.get("experienceCommentaire"))

    # Sous-listes : on les aplatit via _format_list_entries.
    parts.extend(_format_list_entries(
        offer.get("formations"), "Formation",
        ("domaineLibelle", "niveauLibelle", "commentaire"),
    ))
    parts.extend(_format_list_entries(
        offer.get("langues"), "Langue", ("libelle",),
    ))

    # Outils bureautiques : l'API renvoie soit une liste, soit une chaîne.
    outils = offer.get("outilsbureautiques")
    if isinstance(outils, list):
        outils = ", ".join(str(o) for o in outils if o)
    add("Outils bureautiques", outils)

    parts.extend(_format_list_entries(
        offer.get("competences"), "Compétence", ("libelle",),
    ))

    add("Qualification", offer.get("qualificationLibelle"))
    add("Secteur d'activité", offer.get("secteurActiviteLibelle"))

    # Les qualités professionnelles n'ont pas de champ "exigence".
    parts.extend(_format_list_entries(
        offer.get("qualitesProfessionnelles"), "Qualité professionnelle",
        ("libelle", "description"), with_exigence=False,
    ))

    add("Effectif établissement", offer.get("trancheEffectifEtab"))

    # Séparateur double pour faciliter la lecture par Claude.
    return "\n\n".join(parts)

def fetch_france_travail_token(ctx=None) -> str | None:
  
    """Récupère un token OAuth2 client_credentials France Travail.
    Renvoie None si :
      - les credentials ne sont pas configurés (variables d'env vides) ;
      - l'authentification échoue (réseau, identifiants invalides…).
    Le scope demandé donne accès à l'API "Offres d'emploi v2"."""
  
    if not FT_CLIENT_ID or not FT_CLIENT_SECRET:
        if ctx:
            ctx.error("france_travail", "identifiants FT_CLIENT_ID / FT_CLIENT_SECRET absents", fatal=True)
        return None
    try:
        resp = requests.post(
            "https://entreprise.francetravail.fr/connexion/oauth2/access_token",
            params={"realm": "/partenaire"},
            data={
                "grant_type": "client_credentials",
                "client_id": FT_CLIENT_ID,
                "client_secret": FT_CLIENT_SECRET,
                "scope": "api_offresdemploiv2 o2dsoffre",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]
    except Exception as e:
        print(f"  ⚠ France Travail auth échouée : {e}")
        if ctx:
            ctx.error("france_travail", f"authentification : {e}", fatal=True)
        return None

def fetch_france_travail_offers(ctx, token: str) -> list[dict]:
  
    """Interroge l'API France Travail pour chaque mot-clé "ft" de SEARCHES.
    Voir les commentaires inline du dict `params` ci-dessous pour le détail
    de chaque paramètre (commune, distance, pagination, filtre temporel).
    Renvoie une liste de records normalisés (schéma JOBSPY_OUTPUT_COLUMNS),
    déjà dédoublonnés entre eux par titre+recruteur."""
  
    all_offers: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()
    headers = {"Authorization": f"Bearer {token}"}

    # Filtre temporel : depuis le dernier run réussi - 1h de marge de sécurité
    # (au cas où une offre apparaît avec un léger retard côté API).
    cutoff = ctx.since("france_travail")
    min_creation_date = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    # L'API exige maxCreationDate dès que minCreationDate est fourni : sans lui,
    # chaque requête est rejetée (HTTP 400) et France Travail ne ramène rien
    # (c'était le cas du 04/05 au 18/10/2026). On prend "maintenant".
    max_creation_date = now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"  France Travail : {min_creation_date} → {max_creation_date}")

    for entry in ctx.searches:
        # On saute les termes anglais (flag ft=False).
        if not entry.get("ft"):
            continue
        term = entry["term"]
        print(f"  France Travail : '{term}'")
        try:
            resp = requests.get(
                "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search",
                headers=headers,
                params={
                    "motsCles": term,                         # mot-clé de recherche (non exact, voir SEARCHES)
                    "commune": "75056",                       # code INSEE du centre de recherche (Paris) — à adapter à ta zone
                    "distance": 20,                           # rayon de recherche en km
                    "range": f"0-{RESULTATS_PAR_RECHERCHE - 1}",   # pagination : premiers résultats seulement
                    "minCreationDate": min_creation_date,     # filtre temporel : offres créées après cutoff
                    "maxCreationDate": max_creation_date,     # obligatoire avec minCreationDate
                },
                timeout=20,
            )
            # 200 = liste complète, 206 = liste partielle (pagination tronquée).
            # Les deux sont des succès et contiennent des résultats exploitables.
            if resp.status_code in (200, 206):
                data = resp.json()
                results = data.get("resultats", [])
                print(f"    → {len(results)} offres")
                ctx.ok("france_travail", len(results))
                if len(results) >= RESULTATS_PAR_RECHERCHE:
                    ctx.plafond("france_travail", f"'{term}' : {len(results)} résultats")
                for offer in results:
                    # Conversion vers le schéma standard (cf. JOBSPY_OUTPUT_COLUMNS).
                    record = {
                        "title": offer.get("intitule", ""),
                        "recruiter": offer.get("entreprise", {}).get("nom", "Non communiqué"),
                        "location": offer.get("lieuTravail", {}).get("libelle", ""),
                        # Astuce : "télétravail" peut apparaître dans n'importe quel
                        # champ texte (description, conditions, etc.). On sérialise
                        # tout l'offre en JSON pour faire un "contains" insensible
                        # à la casse en une ligne.
                        "is_remote": "télétravail" in json.dumps(offer, ensure_ascii=False).lower(),
                        "job_type": offer.get("typeContrat", ""),
                        "min_amount": offer.get("salaire", {}).get("libelle", ""),
                        "max_amount": None,
                        "currency": "EUR",
                        "date_posted": offer.get("dateCreation", ""),
                        "description": build_description(offer)[:MAX_DESC_CHARS],
                        # urlOrigine = lien vers l'annonce originelle (entreprise),
                        # absent quand l'offre n'est diffusée que sur FT — fallback
                        # sur l'URL canonique candidat.francetravail.fr.
                        "job_url": offer.get("origineOffre", {}).get("urlOrigine", "")
                                   or f"https://candidat.francetravail.fr/offres/recherche/detail/{offer.get('id', '')}",
                        "site": "france_travail",
                        "recherche": "paris",
                        # Identifiant FT : permet de vérifier plus tard si l'offre est toujours en ligne.
                        "id_france_travail": offer.get("id", ""),
                    }
                    # Dédoublonnage local (un même mot-clé peut renvoyer la même offre).
                    key = dedup_key(record)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_offers.append(record)
            elif resp.status_code == 204:
                # 204 No Content = aucun résultat pour ce mot-clé, c'est normal.
                print("    → 0 offre (aucun résultat)")
                ctx.ok("france_travail", 0)
            else:
                print(f"    ⚠ HTTP {resp.status_code} : {resp.text[:200]}")
                ctx.error("france_travail", f"HTTP {resp.status_code} : {resp.text[:150]}")
        except Exception as e:
            # On loggue mais on continue : un mot-clé en échec ne doit pas
            # interrompre les autres.
            print(f"    ⚠ Échec : {e}")
            ctx.error("france_travail", str(e))
            continue
    return all_offers


def fetch_france_travail(ctx) -> list[dict]:
    """France Travail : jeton OAuth2 puis recherche (rien si identifiants absents)."""
    token = fetch_france_travail_token(ctx)
    if not token:
        print("  → France Travail ignoré (identifiants absents ou authentification échouée)")
        return []
    return fetch_france_travail_offers(ctx, token)
