"""
ChatGEO: ARCHS4 Sample Finder and Differential Expression Analysis

A reusable component for finding test and control samples within ARCHS4
and performing differential expression analysis.

## Sample Finding

Two modes of operation:

1. **Pooled Mode** - All matching samples in single test/control groups
   ```python
   from chatgeo import SampleFinder
   finder = SampleFinder()
   pooled = finder.find_pooled_samples("pulmonary fibrosis", tissue="lung")
   # Returns: PooledPair with test_samples and control_samples DataFrames
   # Use for: Single differential expression analysis
   ```

2. **Study-Matched Mode** - Samples grouped by GEO study
   ```python
   matched = finder.find_study_matched_samples("pulmonary fibrosis", tissue="lung")
   # Returns: StudyMatchedResult with list of StudyPair objects
   # Use for: Within-study DE analyses with meta-analysis
   ```

## Differential Expression Analysis

```python
from chatgeo import DifferentialExpressionAnalyzer, DEConfig, ReportGenerator

# Configure and run analysis
config = DEConfig(test_method="mann_whitney_u", fdr_threshold=0.05)
analyzer = DifferentialExpressionAnalyzer(config)
result = analyzer.analyze_pooled(test_expr, control_expr, provenance)

# Generate reports
reporter = ReportGenerator()
reporter.print_summary(result)
reporter.to_json(result, "results.json")
```

## Command Line Interface

```bash
python -m chatgeo.cli "psoriasis in skin tissue" --output results.json
```
"""

from .sample_finder import (
    SampleFinder,
    SampleSet,
    TestControlPair,
    # Pooled mode
    PooledPair,
    # Study-matched mode
    StudyPair,
    StudyMatchedResult,
)
from .query_builder import (
    QueryBuilder,
    QueryExpansion,
    QuerySpec,
    QueryStrategy,
    TextQueryStrategy,
    PatternQueryStrategy,
    OntologyQueryStrategy,
    build_query_spec,
    build_query_spec_fallback,
)
from .study_grouper import StudyGrouper, StudyGroup
from .metrics import SearchMetrics, SearchStats, PairQualityMetrics

# Differential expression analysis
from .de_result import (
    GeneResult,
    DEProvenance,
    DEResult,
    StudyDEResult,
    MetaAnalysisResult,
    # Enrichment result dataclasses
    EnrichedTerm,
    DirectionEnrichment,
    EnrichmentProvenance,
    EnrichmentResult,
)
from .de_analysis import (
    DEConfig,
    DEMethod,
    DifferentialExpressionAnalyzer,
    GeneFilterConfig,
)
from .gene_ranker import (
    GeneRanker,
    RankingConfig,
    RankingMethod,
    rank_by_combined_score,
    filter_by_thresholds,
    separate_by_direction,
)
from .report_generator import (
    ReportGenerator,
    format_gene_table,
    format_provenance_brief,
)
from .enrichment_analyzer import (
    EnrichmentConfig,
    EnrichmentAnalyzer,
    GProfilerBackend,
    run_enrichment,
)
from .species_merger import (
    SpeciesMerger,
    OrthologMapping,
    load_ortholog_table,
)
from .interpretation import interpret_results, save_interpretation, build_prompt
from .cli import parse_query, run_analysis

__all__ = [
    # Core search
    "SampleFinder",
    "SampleSet",
    "TestControlPair",
    # Pooled mode (single DE)
    "PooledPair",
    # Study-matched mode (multiple DEs)
    "StudyPair",
    "StudyMatchedResult",
    # Query building
    "QueryBuilder",
    "QueryExpansion",
    "QuerySpec",
    "QueryStrategy",
    "TextQueryStrategy",
    "PatternQueryStrategy",
    "OntologyQueryStrategy",
    "build_query_spec",
    "build_query_spec_fallback",
    # Study grouping
    "StudyGrouper",
    "StudyGroup",
    # Metrics
    "SearchMetrics",
    "SearchStats",
    "PairQualityMetrics",
    # DE Result dataclasses
    "GeneResult",
    "DEProvenance",
    "DEResult",
    "StudyDEResult",
    "MetaAnalysisResult",
    # Enrichment Result dataclasses
    "EnrichedTerm",
    "DirectionEnrichment",
    "EnrichmentProvenance",
    "EnrichmentResult",
    # DE Analysis
    "DEConfig",
    "DEMethod",
    "DifferentialExpressionAnalyzer",
    "GeneFilterConfig",
    # Gene Ranking
    "GeneRanker",
    "RankingConfig",
    "RankingMethod",
    "rank_by_combined_score",
    "filter_by_thresholds",
    "separate_by_direction",
    # Enrichment Analysis
    "EnrichmentConfig",
    "EnrichmentAnalyzer",
    "GProfilerBackend",
    "run_enrichment",
    # Report Generation
    "ReportGenerator",
    "format_gene_table",
    "format_provenance_brief",
    # Species Merging
    "SpeciesMerger",
    "OrthologMapping",
    "load_ortholog_table",
    # Interpretation
    "interpret_results",
    "save_interpretation",
    "build_prompt",
    # CLI
    "parse_query",
    "run_analysis",
]
