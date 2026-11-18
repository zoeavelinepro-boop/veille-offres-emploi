"""Outils partagés par la collecte, la vérification et les sources (veille/sources/)."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

from veille import lecture_config as config

MAX_DESC_CHARS = config.MAX_DESCRIPTION_CARACTERES   # longueur maximale d'une description (config/sources.yml)

# Identité de navigateur envoyée aux sites interrogés par requête HTTP directe.
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126 Safari/537.36")
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"}


def now_utc() -> datetime:
    """Heure courante en UTC : même résultat sur GitHub Actions et en local."""
    return datetime.now(timezone.utc)


def html_vers_texte(text: str | None) -> str:
    """Convertit du HTML simple en texte brut (paragraphes conservés)."""
    if not text:
        return ""
    txt = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)    # <br> → saut de ligne simple
    txt = re.sub(r"</p>", "\n\n", txt, flags=re.IGNORECASE)        # fin de paragraphe → double saut
    txt = re.sub(r"<[^>]+>", "", txt)                              # toutes les autres balises → supprimées
    txt = re.sub(r"\s*\n\s*", "\n", txt)                           # espaces autour des \n compactés
    txt = re.sub(r"\n{3,}", "\n\n", txt)                           # max 2 \n consécutifs
    return txt.strip()


# Mentions de genre en fin d'intitulé ("H/F", "(F/H/X)", "w/m/d"…), retirées
# avant comparaison. Les variantes les plus longues sont testées d'abord.
_GENDER_RE = re.compile(
    r"[\(\[]?\b(?:h\s*/\s*f\s*/\s*[xd]|f\s*/\s*h\s*/\s*[xd]|w\s*/\s*m\s*/\s*d|m\s*/\s*w\s*/\s*d"
    r"|h\s*/\s*f|f\s*/\s*h|m\s*/\s*f|f\s*/\s*m)\b[\)\]]?",
    re.IGNORECASE,
)


def normaliser(text) -> str:
    """Minuscules, sans accents, sans mention H/F, sans ponctuation, espaces simples."""
    t = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    t = _GENDER_RE.sub(" ", t.lower())
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def dedup_key(record: dict) -> tuple[str, str]:
    """Clé de dédoublonnage (titre, recruteur) normalisée : "Directeur des
    Opérations (H/F)" et "directeur des operations F/H" chez le même
    recruteur donnent la même clé."""
    return (normaliser(record.get("title")), normaliser(record.get("recruiter")))


# =============================================================================
# PRÉ-TRI SUR L'INTITULÉ — liste unique, appliquée à toutes les sources
# =============================================================================
# Pré-tri : offres écartées dès la collecte, sur le seul intitulé, avant toute
# notation par Claude (gratuit). Les listes sont dans config/mots-exclus.yml
# (pour ajouter ou retirer un mot : là seulement) ; la collecte l'applique à
# toutes les sources, et certaines sources s'en servent pour ne pas ouvrir le
# détail des offres déjà exclues (Animal Advocacy Careers, Hellowork).
# Listes vides (config/mots-exclus.yml) : rien n'est exclu. Le motif « (?!) » ne correspond jamais.
_JAMAIS = "(?!)"
PRE_TRI_TITRE_RE = re.compile("|".join(config.PRE_TRI_MOTIFS_TITRE) or _JAMAIS, re.IGNORECASE)
PRE_TRI_EXPRESSIONS = config.PRE_TRI_EXPRESSIONS
PRE_TRI_EXPRESSIONS_RE = re.compile(
    r"(?<![a-z0-9])(?:" + "|".join(re.escape(e) for e in PRE_TRI_EXPRESSIONS) + r")(?![a-z0-9])"
    if PRE_TRI_EXPRESSIONS else _JAMAIS)


def sans_accents(texte: str) -> str:
    """Minuscules, sans accents, apostrophes et tirets remplacés par des espaces."""
    t = unicodedata.normalize("NFD", texte.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[\s'’\-/_,.;:()\[\]]+", " ", t)


MOTS_VIDES = {"le", "la", "les", "l", "de", "du", "des", "d", "a", "au", "aux", "en", "et",
              "of", "the", "and", "for", "to", "in", "an"}


def _jetons(texte: str) -> set[str]:
    """Mots d'un texte, sans accents ni mots vides ; pluriel et singulier confondus."""
    mots = re.findall(r"[a-z0-9]+", sans_accents(str(texte or "")))
    return {m[:-1] if len(m) > 3 and m.endswith("s") else m for m in mots if m not in MOTS_VIDES}


def titre_correspond(titre: str, termes: list[str]) -> bool:
    """Vrai si l'intitulé contient tous les mots d'au moins un des termes de recherche.

    Même logique que les moteurs d'Indeed, LinkedIn ou France Travail : tous les mots du terme
    doivent figurer dans le titre, dans n'importe quel ordre ; les mots vides (de, of, the…),
    les accents et le pluriel sont ignorés ; le féminin et les acronymes ne sont pas unifiés."""
    jetons_titre = _jetons(titre)
    return any(j and j <= jetons_titre for j in (_jetons(t) for t in termes))


def intitule_exclu(titre: str) -> bool:
    """Vrai si l'intitulé relève du pré-tri (stage, junior… ou expression exclue)."""
    titre = str(titre or "")
    return bool(PRE_TRI_TITRE_RE.search(titre) or PRE_TRI_EXPRESSIONS_RE.search(sans_accents(titre)))
