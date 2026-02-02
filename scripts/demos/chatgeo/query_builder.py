"""
Query building with expansion strategies for ARCHS4 sample search.

Supports three strategies:
1. TextQueryStrategy: No expansion (baseline)
2. PatternQueryStrategy: Predefined synonym expansion (fallback)
3. LLM-powered query understanding via build_query_spec() (recommended)

The LLM strategy parses a natural language disease/tissue query into a
structured QuerySpec with disease search terms, tissue include/exclude
filters, and control sample criteria.
"""

import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class QuerySpec:
    """
    Structured query specification for ARCHS4 sample search.

    Produced by the LLM query builder or the pattern-based fallback.
    Drives both the initial ARCHS4 regex search and post-search tissue
    filtering of candidate samples.
    """

    # Search terms
    disease_terms: List[str]
    tissue_include: List[str]
    tissue_exclude: List[str]
    control_terms: List[str]

    # Compiled regex patterns (built from the term lists)
    disease_regex: str
    tissue_include_regex: str
    tissue_exclude_regex: str
    control_regex: str

    # Audit trail
    reasoning: str
    strategy: str  # "llm" or "pattern_fallback"

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "disease_terms": self.disease_terms,
            "tissue_include": self.tissue_include,
            "tissue_exclude": self.tissue_exclude,
            "control_terms": self.control_terms,
            "disease_regex": self.disease_regex,
            "tissue_include_regex": self.tissue_include_regex,
            "tissue_exclude_regex": self.tissue_exclude_regex,
            "control_regex": self.control_regex,
            "reasoning": self.reasoning,
        }


# =========================================================================
# LLM-powered query builder
# =========================================================================

_LLM_SYSTEM_PROMPT = """\
You are a biomedical query parser for the ARCHS4 gene expression database. \
ARCHS4 contains RNA-seq samples from GEO, each annotated with metadata \
fields: title, source_name_ch1, and characteristics_ch1.

Given a disease condition and optional tissue, produce a JSON object that \
will drive sample search and filtering. The goal is to find disease samples \
from the CORRECT tissue and exclude samples from other organs that happen \
to share disease keywords.

Return ONLY valid JSON with these fields:
{
  "disease_terms": ["term1", "term2", ...],
  "tissue_include": ["term1", "term2", ...],
  "tissue_exclude": ["term1", "term2", ...],
  "control_terms": ["term1", "term2", ...],
  "reasoning": "brief explanation"
}

Rules:
- disease_terms: Synonyms and abbreviations for the disease. Include the \
full disease name, common abbreviations, and related terms that would \
appear in GEO sample titles. These are used as an OR regex to search \
ARCHS4 metadata.
- tissue_include: Tissue/organ terms that MUST appear in the sample's \
source_name or title to confirm it is from the correct tissue. These are \
checked AFTER the disease search to filter out off-tissue matches. If no \
tissue constraint, use an empty list.
- tissue_exclude: Tissue/organ terms that should DISQUALIFY a sample. \
These are competing tissues that might share the disease keyword. For \
example, if searching for "pulmonary fibrosis", exclude "liver", "hepatic", \
"kidney", "renal", "cardiac" etc. If the disease is systemic (e.g. lupus \
in blood), the exclude list should be empty or minimal.
- control_terms: Terms describing appropriate healthy control samples for \
this tissue.
- reasoning: One sentence explaining your choices."""


def _term_to_regex(term: str) -> str:
    """Convert a search term to regex, adding word boundaries for short terms.

    Short terms (<=3 characters) like 'RA', 'IPF', 'SLE' get \\b boundaries
    to prevent matching as substrings inside unrelated words (e.g., 'RA'
    inside 'brain', 'library', 'characterization').
    """
    escaped = re.escape(term)
    if len(term) <= 3:
        return r"\b" + escaped + r"\b"
    return escaped


def build_query_spec(
    disease: str,
    tissue: Optional[str] = None,
    model: str = "claude-3-5-haiku-20241022",
) -> QuerySpec:
    """
    Use an LLM to parse a disease/tissue query into structured search criteria.

    Makes one API call to produce disease search terms, tissue include/exclude
    filters, and control sample terms.

    Args:
        disease: Disease or condition name
        tissue: Optional tissue constraint
        model: Anthropic model to use (default: Haiku for speed/cost)

    Returns:
        QuerySpec with structured search and filtering criteria

    Raises:
        ImportError: If anthropic package not installed
        ValueError: If ANTHROPIC_API_KEY not set or LLM returns bad JSON
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    tissue_str = f"\nTissue: {tissue}" if tissue else ""
    user_prompt = f"Disease: {disease}{tissue_str}"

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=512,
        system=_LLM_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Parse the JSON response
    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    spec = json.loads(raw)

    disease_terms = spec["disease_terms"]
    tissue_include = spec.get("tissue_include", [])
    tissue_exclude = spec.get("tissue_exclude", [])
    control_terms = spec.get("control_terms", ["healthy", "control", "normal"])
    reasoning = spec.get("reasoning", "")

    # Ensure broad baseline control terms are always included
    _BASELINE_CONTROL = {"healthy", "control", "normal"}
    control_terms_lower = {t.lower() for t in control_terms}
    for term in _BASELINE_CONTROL:
        if term not in control_terms_lower:
            control_terms.append(term)

    # Build regex patterns from the term lists
    # Short terms (<=3 chars) get word boundaries to prevent substring matches
    # e.g., "RA" should not match inside "brain" or "library"
    disease_regex = "|".join(_term_to_regex(t) for t in disease_terms)
    tissue_include_regex = "|".join(re.escape(t) for t in tissue_include) if tissue_include else ""
    tissue_exclude_regex = "|".join(re.escape(t) for t in tissue_exclude) if tissue_exclude else ""

    # Control regex: broad search, tissue filtering applied separately
    control_regex = "|".join(re.escape(t) for t in control_terms)

    return QuerySpec(
        disease_terms=disease_terms,
        tissue_include=tissue_include,
        tissue_exclude=tissue_exclude,
        control_terms=control_terms,
        disease_regex=disease_regex,
        tissue_include_regex=tissue_include_regex,
        tissue_exclude_regex=tissue_exclude_regex,
        control_regex=control_regex,
        reasoning=reasoning,
        strategy="llm",
    )


def build_query_spec_fallback(
    disease: str,
    tissue: Optional[str] = None,
) -> QuerySpec:
    """
    Build a QuerySpec using the pattern-based strategy (no LLM).

    Used as a fallback when no API key is available. Applies tissue
    conjunction to the disease search when a tissue is specified.

    Args:
        disease: Disease or condition name
        tissue: Optional tissue constraint

    Returns:
        QuerySpec with pattern-based search criteria
    """
    strategy = PatternQueryStrategy()

    # Expand disease terms
    disease_exp = strategy.expand(disease)
    disease_terms = disease_exp.expanded_terms

    # Expand tissue terms
    tissue_include = []
    tissue_exclude = []
    if tissue:
        tissue_exp = strategy.expand(tissue)
        tissue_include = tissue_exp.expanded_terms

    disease_regex = "|".join(_term_to_regex(t) for t in disease_terms)
    tissue_include_regex = "|".join(re.escape(t) for t in tissue_include) if tissue_include else ""

    control_terms = ["healthy", "control", "normal"]
    control_regex = "|".join(re.escape(t) for t in control_terms)

    return QuerySpec(
        disease_terms=disease_terms,
        tissue_include=tissue_include,
        tissue_exclude=tissue_exclude,
        control_terms=control_terms,
        disease_regex=disease_regex,
        tissue_include_regex=tissue_include_regex,
        tissue_exclude_regex="",
        control_regex=control_regex,
        reasoning="Pattern-based fallback (no LLM available)",
        strategy="pattern_fallback",
    )


# =========================================================================
# Legacy strategy classes (kept for backward compatibility)
# =========================================================================


@dataclass
class QueryExpansion:
    """Holds expansion results for a query term."""

    original_term: str
    expanded_terms: List[str]
    strategy_name: str

    @property
    def all_terms(self) -> List[str]:
        """Return original term plus all expanded terms."""
        return [self.original_term] + [
            t for t in self.expanded_terms if t != self.original_term
        ]

    def to_regex(self) -> str:
        """Convert expanded terms to regex pattern."""
        if not self.expanded_terms:
            return self.original_term
        return "|".join(self.all_terms)


class QueryStrategy(ABC):
    """Abstract base class for query expansion strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return strategy name for tracking."""
        pass

    @abstractmethod
    def expand(self, term: str) -> QueryExpansion:
        """Expand a search term into related terms."""
        pass


class TextQueryStrategy(QueryStrategy):
    """Baseline strategy - no expansion, returns term unchanged."""

    @property
    def name(self) -> str:
        return "text"

    def expand(self, term: str) -> QueryExpansion:
        return QueryExpansion(
            original_term=term,
            expanded_terms=[term],
            strategy_name=self.name,
        )


class PatternQueryStrategy(QueryStrategy):
    """
    Pattern-based expansion using predefined synonyms and related terms.

    Useful for well-known disease/tissue synonyms without needing
    ontology lookups.
    """

    # Predefined patterns for common biomedical terms
    PATTERNS = {
        # Tissue synonyms
        "lung": ["lung", "pulmonary", "respiratory"],
        "liver": ["liver", "hepatic", "hepato"],
        "kidney": ["kidney", "renal", "nephro"],
        "brain": ["brain", "cerebral", "neural", "neuro"],
        "heart": ["heart", "cardiac", "cardio"],
        "skin": ["skin", "dermal", "cutaneous", "epidermal"],
        "blood": ["blood", "hematopoietic", "hematological"],
        "bone": ["bone", "osseous", "skeletal"],
        "muscle": ["muscle", "muscular", "myogenic"],
        "intestine": ["intestine", "intestinal", "gut", "enteric", "colon", "colonic"],
        # Disease modifiers
        "fibrosis": ["fibrosis", "fibrotic", "scarring"],
        "inflammation": ["inflammation", "inflammatory", "inflamed"],
        "cancer": ["cancer", "carcinoma", "tumor", "tumour", "malignant", "neoplasm"],
        "arthritis": ["arthritis", "arthritic"],
        # Common disease synonyms
        "copd": ["copd", "chronic obstructive pulmonary disease"],
        "ibd": ["ibd", "inflammatory bowel disease"],
        "ra": ["rheumatoid arthritis", "ra"],
        "ipf": ["idiopathic pulmonary fibrosis", "ipf"],
    }

    @property
    def name(self) -> str:
        return "pattern"

    def expand(self, term: str) -> QueryExpansion:
        term_lower = term.lower()
        expanded = set()

        # Check if term matches any pattern keys or values
        for key, synonyms in self.PATTERNS.items():
            if term_lower == key or term_lower in synonyms:
                expanded.update(synonyms)
                break

        # Also check for partial matches in compound terms
        # Use word boundary check to avoid substring collisions
        # (e.g., "ra" matching inside "brain")
        for key, synonyms in self.PATTERNS.items():
            if len(key) <= 2:
                # Short keys must match as whole words
                if re.search(r'\b' + re.escape(key) + r'\b', term_lower):
                    expanded.update(synonyms)
            elif key in term_lower:
                expanded.update(synonyms)

        # Always include the original term
        expanded.add(term)

        return QueryExpansion(
            original_term=term,
            expanded_terms=sorted(list(expanded)),
            strategy_name=self.name,
        )


class OntologyQueryStrategy(QueryStrategy):
    """
    Placeholder for ontology-based expansion using MONDO/UBERON.

    This strategy will query ontology services to find:
    - MONDO disease synonyms and related terms
    - UBERON tissue/anatomy synonyms

    Current implementation falls back to pattern matching.
    """

    def __init__(self):
        self._pattern_fallback = PatternQueryStrategy()

    @property
    def name(self) -> str:
        return "ontology"

    def expand(self, term: str) -> QueryExpansion:
        # TODO: Implement MONDO/UBERON query expansion
        # For now, fall back to pattern strategy
        result = self._pattern_fallback.expand(term)
        return QueryExpansion(
            original_term=result.original_term,
            expanded_terms=result.expanded_terms,
            strategy_name=self.name,
        )


@dataclass
class QueryBuilder:
    """
    Builds search queries with configurable expansion strategies.

    Example:
        builder = QueryBuilder(strategy=PatternQueryStrategy())
        pattern = builder.build_disease_query("pulmonary fibrosis")
        # Returns: "pulmonary|lung|respiratory.*fibrosis|fibrotic|scarring"
    """

    strategy: QueryStrategy = field(default_factory=TextQueryStrategy)
    default_control_keywords: List[str] = field(
        default_factory=lambda: ["healthy", "control", "normal"]
    )

    def build_disease_query(self, disease_term: str) -> str:
        """
        Build a regex pattern for disease search.

        Args:
            disease_term: Disease name or description

        Returns:
            Regex pattern for searching ARCHS4 metadata
        """
        expansion = self.strategy.expand(disease_term)
        return expansion.to_regex()

    def build_tissue_query(self, tissue_term: str) -> str:
        """
        Build a regex pattern for tissue search.

        Args:
            tissue_term: Tissue name

        Returns:
            Regex pattern for searching ARCHS4 metadata
        """
        expansion = self.strategy.expand(tissue_term)
        return expansion.to_regex()

    def build_control_query(
        self,
        tissue_term: Optional[str] = None,
        control_keywords: Optional[List[str]] = None,
    ) -> str:
        """
        Build a regex pattern for control sample search.

        Combines tissue terms (if provided) with control keywords.

        Args:
            tissue_term: Optional tissue to constrain control search
            control_keywords: Keywords indicating control samples
                             (default: healthy, control, normal)

        Returns:
            Regex pattern for searching ARCHS4 metadata
        """
        keywords = control_keywords or self.default_control_keywords

        if tissue_term:
            tissue_expansion = self.strategy.expand(tissue_term)
            tissue_pattern = tissue_expansion.to_regex()
            keyword_pattern = "|".join(keywords)
            # Match tissue AND control keywords
            return f"({tissue_pattern}).*({keyword_pattern})"
        else:
            return "|".join(keywords)

    def get_expansion_info(self, term: str) -> QueryExpansion:
        """
        Get detailed expansion info for a term without building full query.

        Useful for debugging and metrics.
        """
        return self.strategy.expand(term)
