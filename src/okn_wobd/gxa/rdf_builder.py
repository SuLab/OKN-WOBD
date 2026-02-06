"""
GXA RDF builder — bridges pipeline DataFrames to de_rdf TurtleWriter.

Translates GXA extraction results into the unified Biolink RDF pattern
shared with ChatGEO/de_rdf, using TurtleWriter for graph construction.

Key relationship translations (spoke-genelab → de_rdf):
  Study-PERFORMED-Assay       → HAS_OUTPUT
  Study-HAS_DISEASE-Disease   → STUDIES
  Assay-MEASURED_DE-Gene      → MEASURED_DIFFERENTIAL_EXPRESSION (reified)
  Assay→GOTerm/Pathway        → ENRICHED_IN (reified, 1-hop)
  Assay→Anatomy/CellType/etc  → HAS_ATTRIBUTE
"""

import re
from typing import Dict, Optional

import pandas as pd
from rdflib import URIRef

from okn_wobd.de_rdf.config import (
    OKN_WOBD,
    NCBIGENE,
    ENSEMBL,
    NCBITAXON,
    GO,
    REACTOME,
    INTERPRO,
    UBERON,
    MONDO,
    CL,
    PATO,
    EFO,
    HANCESTRO,
    create_node_uri,
    sanitize_uri_identifier,
)
from okn_wobd.de_rdf.turtle_writer import TurtleWriter


def _gene_uri(identifier: str, id_source: str = "") -> URIRef:
    """Build a gene URI from an identifier, using NCBI or Ensembl namespace."""
    if id_source == "NCBIGene" or (identifier and identifier.isdigit()):
        return URIRef(f"{NCBIGENE}{identifier}")
    if identifier and identifier.startswith("ENSG"):
        return URIRef(f"{ENSEMBL}{identifier}")
    if identifier and identifier.startswith("ENSMUS"):
        return URIRef(f"{ENSEMBL}{identifier}")
    # Fallback for any Ensembl-style ID
    if identifier and identifier.startswith("ENS"):
        return URIRef(f"{ENSEMBL}{identifier}")
    return URIRef(f"{NCBIGENE}{identifier}")


def _ontology_uri(raw_uri: str) -> Optional[URIRef]:
    """Convert an ontology URI string to a URIRef, normalizing common patterns."""
    if not raw_uri or raw_uri == "nan":
        return None

    # Already a full URI
    if raw_uri.startswith("http://") or raw_uri.startswith("https://"):
        return URIRef(raw_uri)

    # GO:0000001 → http://purl.obolibrary.org/obo/GO_0000001
    if raw_uri.startswith("GO:"):
        return URIRef(f"http://purl.obolibrary.org/obo/GO_{raw_uri[3:]}")

    # R-HSA-12345 → Reactome
    if raw_uri.startswith("R-"):
        return URIRef(f"{REACTOME}{raw_uri}")

    # IPR000001 → InterPro
    if raw_uri.startswith("IPR"):
        return URIRef(f"{INTERPRO}{raw_uri}")

    # UBERON:0000001
    if raw_uri.startswith("UBERON:"):
        return URIRef(f"http://purl.obolibrary.org/obo/UBERON_{raw_uri[7:]}")

    # MONDO:0000001
    if raw_uri.startswith("MONDO:"):
        return URIRef(f"http://purl.obolibrary.org/obo/MONDO_{raw_uri[6:]}")

    # CL:0000001
    if raw_uri.startswith("CL:"):
        return URIRef(f"http://purl.obolibrary.org/obo/CL_{raw_uri[3:]}")

    return None


def _enrichment_source(enrichment_type: str) -> str:
    """Map enrichment type to a source label."""
    return {
        "go": "GXA:GO",
        "reactome": "GXA:Reactome",
        "interpro": "GXA:InterPro",
    }.get(enrichment_type, f"GXA:{enrichment_type}")


def _enrichment_node_type(enrichment_type: str) -> str:
    """Map enrichment type to a node type."""
    return {
        "go": "GOTerm",
        "reactome": "ReactomePathway",
        "interpro": "InterProDomain",
    }.get(enrichment_type, "GOTerm")


def build_rdf_from_pipeline_result(
    result,
    gsea_results: Optional[pd.DataFrame],
    accession: str,
) -> TurtleWriter:
    """
    Build a TurtleWriter graph from a GXA pipeline result.

    This is the central function that translates spoke-genelab-style
    DataFrames into the de_rdf unified pattern.

    Args:
        result: GXAPipelineResult with .nodes and .relationships dicts
        gsea_results: Flat DataFrame from extract_gsea_results()
        accession: Experiment accession (e.g. "E-GEOD-5305")

    Returns:
        TurtleWriter with the complete RDF graph for this experiment
    """
    writer = TurtleWriter()

    # ── Study node ────────────────────────────────────────────────
    study_uri = create_node_uri("study", accession)

    study_df = result.nodes.get("Study")
    study_props = {}
    if study_df is not None and not study_df.empty:
        row = study_df.iloc[0]
        for col in ["name", "description", "project_title", "organism",
                     "source", "submitter_name", "pubmed_id"]:
            val = row.get(col)
            if val and pd.notna(val) and str(val).strip():
                study_props[col] = str(val)
        # List fields
        for col in ["experimental_factors", "secondary_accessions"]:
            val = row.get(col)
            if val is not None:
                if isinstance(val, list):
                    study_props[col] = ", ".join(str(v) for v in val)
                elif pd.notna(val) and str(val).strip():
                    study_props[col] = str(val)

    writer.add_node(study_uri, "Study", study_props)

    # ── Taxon node & Study→Taxon ──────────────────────────────────
    taxonomy = ""
    if study_df is not None and not study_df.empty:
        taxonomy = str(study_df.iloc[0].get("taxonomy", ""))
    if taxonomy and taxonomy != "nan":
        taxon_uri = URIRef(f"{NCBITAXON}{taxonomy}")
        writer.add_node(taxon_uri, "OrganismTaxon", {"name": study_props.get("organism", "")})
        writer.add_relationship(study_uri, "IN_TAXON", taxon_uri)

    # ── Disease nodes & Study→Disease (STUDIES) ───────────────────
    study_disease_df = result.relationships.get("Study-STUDIES-Disease",
                       result.relationships.get("Study-HAS_DISEASE-Disease"))
    disease_df = result.nodes.get("Disease")
    if disease_df is not None and not disease_df.empty:
        for _, row in disease_df.iterrows():
            uri_str = str(row.get("identifier", ""))
            uri = _ontology_uri(uri_str) or URIRef(uri_str)
            name = str(row.get("name", "")) if pd.notna(row.get("name")) else ""
            writer.add_node(uri, "Disease", {"name": name} if name else {})

    if study_disease_df is not None and not study_disease_df.empty:
        for _, row in study_disease_df.iterrows():
            to_str = str(row["to"])
            to_uri = _ontology_uri(to_str) or URIRef(to_str)
            writer.add_relationship(study_uri, "STUDIES", to_uri)

    # ── Study-level characteristic relationships (HAS_ATTRIBUTE) ──
    _add_study_characteristic_rels(writer, result, study_uri, "Sex")
    _add_study_characteristic_rels(writer, result, study_uri, "DevelopmentalStage")
    _add_study_characteristic_rels(writer, result, study_uri, "EthnicGroup")
    _add_study_characteristic_rels(writer, result, study_uri, "OrganismStatus")

    # ── Assay nodes & Study→Assay (HAS_OUTPUT) ────────────────────
    assay_df = result.nodes.get("Assay")
    if assay_df is not None and not assay_df.empty:
        for _, row in assay_df.iterrows():
            assay_id = str(row["identifier"])
            assay_uri = create_node_uri("assay", assay_id)

            assay_props = {}
            for col in ["name", "contrast_id", "technology", "array_design"]:
                val = row.get(col)
                if val and pd.notna(val) and str(val).strip():
                    assay_props[col] = str(val)

            writer.add_node(assay_uri, "Assay", assay_props)
            writer.add_relationship(study_uri, "HAS_OUTPUT", assay_uri)

    # ── Anatomy & CellType nodes ──────────────────────────────────
    for node_type in ["Anatomy", "CellType"]:
        node_df = result.nodes.get(node_type)
        if node_df is not None and not node_df.empty:
            for _, row in node_df.iterrows():
                uri_str = str(row.get("identifier", ""))
                uri = _ontology_uri(uri_str) or URIRef(uri_str)
                name = str(row.get("name", "")) if pd.notna(row.get("name")) else ""
                writer.add_node(uri, node_type, {"name": name} if name else {})

    # ── Assay-level HAS_ATTRIBUTE relationships ───────────────────
    for rel_key, rel_df in result.relationships.items():
        if not rel_key.startswith("Assay-HAS_ATTRIBUTE"):
            continue
        if rel_df is None or rel_df.empty:
            continue
        for _, row in rel_df.iterrows():
            from_id = str(row["from"])
            to_str = str(row["to"])
            assay_uri = create_node_uri("assay", from_id)
            to_uri = _ontology_uri(to_str) or URIRef(to_str)
            writer.add_relationship(assay_uri, "HAS_ATTRIBUTE", to_uri)

    # ── Gene nodes ────────────────────────────────────────────────
    mgene_df = result.nodes.get("MGene")
    if mgene_df is not None and not mgene_df.empty:
        for _, row in mgene_df.iterrows():
            identifier = str(row["identifier"])
            id_source = str(row.get("id_source", ""))
            gene_uri = _gene_uri(identifier, id_source)

            gene_props = {}
            symbol = row.get("symbol")
            if symbol and pd.notna(symbol) and str(symbol).strip():
                gene_props["symbol"] = str(symbol)
            ensembl_id = row.get("ensembl_id")
            if ensembl_id and pd.notna(ensembl_id):
                gene_props["id"] = str(ensembl_id)

            writer.add_node(gene_uri, "MGene", gene_props)

    # ── Differential expression (MEASURED_DIFFERENTIAL_EXPRESSION) ─
    de_df = result.relationships.get("Assay-MEASURED_DIFFERENTIAL_EXPRESSION_ASmMG-MGene")
    if de_df is not None and not de_df.empty:
        # Build gene identifier → id_source lookup
        id_source_map: Dict[str, str] = {}
        if mgene_df is not None and not mgene_df.empty:
            for _, row in mgene_df.iterrows():
                id_source_map[str(row["identifier"])] = str(row.get("id_source", ""))

        for _, row in de_df.iterrows():
            assay_id = str(row["from"])
            gene_id = str(row["to"])
            assay_uri = create_node_uri("assay", assay_id)
            gene_uri = _gene_uri(gene_id, id_source_map.get(gene_id, ""))

            props = {}
            for col in ["log2fc", "adj_p_value"]:
                val = row.get(col)
                if val is not None and pd.notna(val):
                    props[col] = float(val)

            # Add direction based on log2fc
            if "log2fc" in props:
                props["direction"] = "up" if props["log2fc"] > 0 else "down"

            writer.add_relationship(
                assay_uri, "MEASURED_DIFFERENTIAL_EXPRESSION", gene_uri, props
            )

    # ── GSEA Enrichment (ENRICHED_IN, 1-hop reified) ─────────────
    if gsea_results is not None and not gsea_results.empty:
        _add_enrichment_triples(writer, gsea_results, accession)

    return writer


def _add_study_characteristic_rels(
    writer: TurtleWriter,
    result,
    study_uri: URIRef,
    node_type: str,
) -> None:
    """Add study-level characteristic nodes and HAS_ATTRIBUTE relationships."""
    node_df = result.nodes.get(node_type)
    if node_df is not None and not node_df.empty:
        for _, row in node_df.iterrows():
            uri_str = str(row.get("identifier", ""))
            uri = _ontology_uri(uri_str) or URIRef(uri_str)
            name = str(row.get("name", "")) if pd.notna(row.get("name")) else ""
            writer.add_node(uri, node_type, {"name": name} if name else {})
            writer.add_relationship(study_uri, "HAS_ATTRIBUTE", uri)


def _add_enrichment_triples(
    writer: TurtleWriter,
    gsea_results: pd.DataFrame,
    accession: str,
) -> None:
    """Add 1-hop ENRICHED_IN associations from flat GSEA results."""
    # First, add term nodes
    seen_terms = set()
    for _, row in gsea_results.iterrows():
        term_id = row.get("term_id", row.get("Accession", ""))
        if not term_id or pd.isna(term_id) or str(term_id) in seen_terms:
            continue

        term_id_str = str(term_id)
        seen_terms.add(term_id_str)

        enrichment_type = str(row.get("enrichment_type", "go"))
        node_type = _enrichment_node_type(enrichment_type)

        term_uri = _ontology_uri(term_id_str)
        if term_uri is None:
            continue

        term_name = row.get("term_name", row.get("Term", ""))
        term_props = {"name": str(term_name)} if term_name and pd.notna(term_name) else {}

        writer.add_node(term_uri, node_type, term_props)

    # Then, add ENRICHED_IN relationships (Assay → Term)
    for _, row in gsea_results.iterrows():
        term_id = row.get("term_id", row.get("Accession", ""))
        if not term_id or pd.isna(term_id):
            continue

        term_uri = _ontology_uri(str(term_id))
        if term_uri is None:
            continue

        contrast_id = str(row.get("contrast_id", ""))
        if not contrast_id:
            continue

        assay_id = f"{accession}-{contrast_id}"
        assay_uri = create_node_uri("assay", assay_id)

        enrichment_type = str(row.get("enrichment_type", "go"))

        props: Dict[str, object] = {
            "enrichment_source": _enrichment_source(enrichment_type),
        }

        for col in ["adj_p_value", "p_value", "effect_size"]:
            val = row.get(col)
            if val is not None and pd.notna(val):
                props[col] = float(val)

        # Determine direction from effect size
        if "effect_size" in props:
            es = float(props["effect_size"])
            props["direction"] = "up" if es > 0 else "down"

        writer.add_relationship(assay_uri, "ENRICHED_IN", term_uri, props)
