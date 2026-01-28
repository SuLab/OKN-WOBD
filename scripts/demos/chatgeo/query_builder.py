"""
Query building with expansion strategies for ARCHS4 sample search.

Provides text-based search with architecture prepared for ontology-based
query expansion (MONDO for diseases, UBERON for tissues).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


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
        for key, synonyms in self.PATTERNS.items():
            if key in term_lower:
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
