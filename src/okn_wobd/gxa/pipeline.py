"""
GXA Pipeline orchestrator.

Processes GXA experiment directories and produces harmonized RDF output
using the de_rdf TurtleWriter infrastructure.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd

from .parser import GEAExperiment, load_gea_experiment
from .study_extractor import extract_study_nodes, get_study_summary
from .gene_extractor import create_mgene_nodes, extract_differential_expression
from .assay_extractor import (
    extract_assay_nodes,
    extract_sdrf_characteristics,
    extract_factor_values_per_assay_group,
    extract_characteristics_per_assay_group,
    create_disease_nodes,
    create_sex_nodes,
    create_developmental_stage_nodes,
    create_ethnic_group_nodes,
    create_organism_status_nodes,
    create_anatomy_nodes_from_sdrf,
    create_celltype_nodes_from_sdrf,
    create_study_disease_relationships,
    create_study_sex_relationships,
    create_study_developmental_stage_relationships,
    create_study_ethnic_group_relationships,
    create_study_organism_status_relationships,
    create_assay_characteristic_relationships,
    create_assay_factor_relationships,
)
from .gsea_extractor import extract_gsea_results
from .rdf_builder import build_rdf_from_pipeline_result


class GXAPipelineResult:
    """Container for GXA pipeline results."""

    def __init__(self):
        self.nodes: Dict[str, pd.DataFrame] = {}
        self.relationships: Dict[str, pd.DataFrame] = {}
        self.experiment: Optional[GEAExperiment] = None
        self.gsea_results: Optional[pd.DataFrame] = None
        self.errors: List[str] = []

    def add_nodes(self, node_type: str, df: pd.DataFrame):
        if df.empty:
            return
        if node_type in self.nodes:
            self.nodes[node_type] = pd.concat(
                [self.nodes[node_type], df], ignore_index=True
            ).drop_duplicates(subset="identifier" if "identifier" in df.columns else None)
        else:
            self.nodes[node_type] = df

    def add_relationships(self, rel_type: str, df: pd.DataFrame):
        if df.empty:
            return
        if rel_type in self.relationships:
            self.relationships[rel_type] = pd.concat(
                [self.relationships[rel_type], df], ignore_index=True
            ).drop_duplicates()
        else:
            self.relationships[rel_type] = df

    def get_stats(self) -> Dict[str, int]:
        stats = {}
        for node_type, df in self.nodes.items():
            stats[f"nodes_{node_type}"] = len(df)
        for rel_type, df in self.relationships.items():
            stats[f"relationships_{rel_type}"] = len(df)
        return stats


def process_gxa_experiment(
    experiment_dir: Union[str, Path],
    p_value_threshold: float = 0.01,
    max_genes_per_assay: int = 200,
    max_terms_per_type: int = 20,
    include_gsea: bool = True,
) -> GXAPipelineResult:
    """
    Process a single GXA experiment directory.

    Args:
        experiment_dir: Path to experiment directory
        p_value_threshold: Adjusted p-value threshold for filtering
        max_genes_per_assay: Max DE genes per assay
        max_terms_per_type: Max enriched terms per type per contrast
        include_gsea: Whether to include GSEA/pathway enrichment data

    Returns:
        GXAPipelineResult with all nodes and relationships
    """
    result = GXAPipelineResult()

    # Load experiment
    print(f"Loading experiment from {experiment_dir}")
    try:
        experiment = load_gea_experiment(str(experiment_dir))
        result.experiment = experiment
    except Exception as e:
        result.errors.append(f"Failed to load experiment: {e}")
        return result

    summary = get_study_summary(experiment)
    print(f"  Accession: {summary['accession']}")
    print(f"  Title: {summary['title']}")
    print(f"  Organism: {summary['organism']}")
    print(f"  Contrasts: {summary['num_contrasts']}")

    # Extract Study nodes
    print("Extracting Study nodes...")
    study_nodes = extract_study_nodes(experiment)
    result.add_nodes("Study", study_nodes)

    # Extract Assay nodes
    print("Extracting Assay nodes...")
    assay_nodes = extract_assay_nodes(experiment)
    result.add_nodes("Assay", assay_nodes)

    # Extract SDRF characteristics and factors
    print("Extracting SDRF characteristics and factors...")
    characteristics = extract_sdrf_characteristics(experiment)
    group_factors = extract_factor_values_per_assay_group(experiment)
    group_characteristics = extract_characteristics_per_assay_group(experiment)

    # Create characteristic nodes
    result.add_nodes("Disease", create_disease_nodes(characteristics))
    result.add_nodes("Sex", create_sex_nodes(characteristics))
    result.add_nodes("DevelopmentalStage", create_developmental_stage_nodes(characteristics))
    result.add_nodes("EthnicGroup", create_ethnic_group_nodes(characteristics))
    result.add_nodes("OrganismStatus", create_organism_status_nodes(characteristics))
    result.add_nodes("Anatomy", create_anatomy_nodes_from_sdrf(characteristics))
    result.add_nodes("CellType", create_celltype_nodes_from_sdrf(characteristics))

    # Create Study-Disease relationships (→ STUDIES)
    study_id = experiment.accession
    result.add_relationships(
        "Study-STUDIES-Disease",
        create_study_disease_relationships(study_id, characteristics),
    )

    # Create Study-characteristic relationships (→ HAS_ATTRIBUTE)
    result.add_relationships(
        "Study-HAS_ATTRIBUTE-Sex",
        create_study_sex_relationships(study_id, characteristics),
    )
    result.add_relationships(
        "Study-HAS_ATTRIBUTE-DevelopmentalStage",
        create_study_developmental_stage_relationships(study_id, characteristics),
    )
    result.add_relationships(
        "Study-HAS_ATTRIBUTE-EthnicGroup",
        create_study_ethnic_group_relationships(study_id, characteristics),
    )
    result.add_relationships(
        "Study-HAS_ATTRIBUTE-OrganismStatus",
        create_study_organism_status_relationships(study_id, characteristics),
    )

    # Assay-level relationships (all → HAS_ATTRIBUTE)
    # CellType from characteristics
    result.add_relationships(
        "Assay-HAS_ATTRIBUTE-CellType",
        create_assay_characteristic_relationships(
            assay_nodes, group_characteristics, "cell type", "CellType"
        ),
    )
    # Anatomy from characteristics
    result.add_relationships(
        "Assay-HAS_ATTRIBUTE-Anatomy",
        create_assay_characteristic_relationships(
            assay_nodes, group_characteristics, "organism part", "Anatomy"
        ),
    )
    # Anatomy from factors
    result.add_relationships(
        "Assay-HAS_ATTRIBUTE-Anatomy",
        create_assay_factor_relationships(
            assay_nodes, group_factors, "organism part", "Anatomy"
        ),
    )
    # CellType from factors
    result.add_relationships(
        "Assay-HAS_ATTRIBUTE-CellType",
        create_assay_factor_relationships(
            assay_nodes, group_factors, "cell type", "CellType"
        ),
    )
    # Disease from factors (assay-level)
    result.add_relationships(
        "Assay-HAS_ATTRIBUTE-Disease",
        create_assay_factor_relationships(
            assay_nodes, group_factors, "disease", "Disease"
        ),
    )

    # Extract gene nodes
    print("Extracting gene nodes...")
    mgene_nodes = create_mgene_nodes(experiment)
    result.add_nodes("MGene", mgene_nodes)

    # Extract differential expression
    print("Extracting differential expression data...")
    de_rels = extract_differential_expression(
        experiment, p_value_threshold, max_genes_per_assay
    )
    result.add_relationships(
        "Assay-MEASURED_DIFFERENTIAL_EXPRESSION_ASmMG-MGene", de_rels
    )

    # Extract GSEA
    if include_gsea:
        print("Extracting GSEA/pathway enrichment data...")
        gsea_results = extract_gsea_results(
            experiment, p_value_threshold, max_terms_per_type
        )
        result.gsea_results = gsea_results

    # Print stats
    stats = result.get_stats()
    print("\nPipeline Results:")
    for key, count in sorted(stats.items()):
        print(f"  {key}: {count}")

    return result


def run_gxa_rdf_pipeline(
    data_dir: Union[str, Path],
    output_dir: Union[str, Path],
    experiment: Optional[str] = None,
    p_value_threshold: float = 0.01,
    max_genes_per_assay: int = 200,
    max_terms_per_type: int = 20,
    include_gsea: bool = True,
) -> None:
    """
    Main entry point for GXA→RDF pipeline.

    Processes experiment directories and writes one .ttl per experiment.
    Already-processed experiments (existing .ttl files) are skipped.

    Args:
        data_dir: Directory containing experiment subdirectories (*-gea/)
        output_dir: Output directory for .ttl files
        experiment: Single experiment accession to process (optional)
        p_value_threshold: P-value threshold for DE/GSEA filtering
        max_genes_per_assay: Max DE genes per assay
        max_terms_per_type: Max GSEA terms per type per contrast
        include_gsea: Whether to include GSEA data
    """
    data_path = Path(data_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if experiment:
        # Single experiment
        exp_dirs = []
        # Try exact directory name
        for suffix in ["-gea", ""]:
            candidate = data_path / f"{experiment}{suffix}"
            if candidate.is_dir():
                exp_dirs = [candidate]
                break
        if not exp_dirs:
            # Search for directory containing the experiment name
            for d in data_path.iterdir():
                if d.is_dir() and experiment in d.name:
                    exp_dirs = [d]
                    break
        if not exp_dirs:
            print(f"Error: Could not find experiment directory for {experiment}")
            return
    else:
        # Batch: find all experiment directories
        exp_dirs = sorted([
            d for d in data_path.iterdir()
            if d.is_dir() and d.name.endswith("-gea")
        ])

    total = len(exp_dirs)

    # Check which experiments already have RDF files
    existing_rdf = {f.stem for f in output_path.glob("*.ttl")}
    remaining_dirs = [
        d for d in exp_dirs
        if d.name.replace("-gea", "") not in existing_rdf
    ]
    skipped = total - len(remaining_dirs)

    print(f"Found {total} experiment directories")
    if skipped > 0:
        print(f"Skipping {skipped} already processed (RDF files exist)")
    print(f"Processing {len(remaining_dirs)} remaining experiments")
    print("=" * 60)

    processed = 0
    failed = 0
    start_time = time.time()

    for i, exp_dir in enumerate(remaining_dirs, 1):
        exp_name = exp_dir.name
        accession = exp_name.replace("-gea", "")
        rdf_name = f"{accession}.ttl"

        try:
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 and processed > 0 else 0
            remaining = len(remaining_dirs) - i
            eta = remaining / rate if rate > 0 else 0

            total_done = skipped + i
            print(f"\n[{total_done}/{total}] {exp_name} -> {rdf_name} (ETA: {eta/60:.1f} min)")

            exp_result = process_gxa_experiment(
                exp_dir,
                p_value_threshold=p_value_threshold,
                max_genes_per_assay=max_genes_per_assay,
                max_terms_per_type=max_terms_per_type,
                include_gsea=include_gsea,
            )

            if exp_result.errors:
                for error in exp_result.errors:
                    print(f"  WARNING: {error}")
                failed += 1
                continue

            # Build RDF using de_rdf TurtleWriter
            writer = build_rdf_from_pipeline_result(
                exp_result, exp_result.gsea_results, accession
            )

            rdf_file = output_path / rdf_name
            writer.write(rdf_file)
            triple_count = writer.get_triple_count()
            print(f"  Wrote {rdf_file} ({triple_count:,} triples)")
            processed += 1

        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

    # Print summary
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("BATCH PROCESSING COMPLETE")
    print(f"  Total experiments: {total}")
    print(f"  Already processed: {skipped}")
    print(f"  Processed this run: {processed}")
    print(f"  Failed: {failed}")
    print(f"  Time: {elapsed/60:.1f} minutes")
    print(f"  Output directory: {output_path}")
    print("=" * 60)
