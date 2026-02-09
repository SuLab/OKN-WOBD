"""Biolink-based RDF export for differential expression results.

Provides a reusable library for converting DE analysis results into
RDF following the Biolink Model. Gene symbols are resolved to NCBI
Gene IDs via a local HGNC cache.

Usage::

    from okn_wobd.de_rdf import DEExperiment, DEGene, RdfConfig, build_rdf

    experiment = DEExperiment(
        id="psoriasis_skin_20260202",
        name="DE: psoriasis in skin",
        genes=[DEGene(gene_symbol="IDO1", log2_fold_change=6.96, ...)],
    )
    writer = build_rdf(experiment)
    writer.write("output.ttl")
"""

from okn_wobd.de_rdf.config import RdfConfig
from okn_wobd.de_rdf.experiment_builder import build_rdf
from okn_wobd.de_rdf.gene_mapper import GeneMapper
from okn_wobd.de_rdf.model import DEExperiment, DEGene, EnrichmentAssociation
from okn_wobd.de_rdf.turtle_writer import TurtleWriter

__all__ = [
    "RdfConfig",
    "DEExperiment",
    "DEGene",
    "EnrichmentAssociation",
    "build_rdf",
    "GeneMapper",
    "TurtleWriter",
]
