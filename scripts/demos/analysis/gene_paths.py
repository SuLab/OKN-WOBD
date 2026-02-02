#!/usr/bin/env python3
"""
Gene-Disease Path Finder

Finds connections between a gene and diseases using multiple knowledge graphs:
1. SPOKE-OKN: Direct gene-disease associations
2. Wikidata: Gene → Protein → GO terms, Gene → Disease associations
3. Ubergraph: GO term → Disease relationships via ontology

Path types discovered:
- Gene -[MARKER_POS]-> Disease (SPOKE: positive marker)
- Gene -[MARKER_NEG]-> Disease (SPOKE: negative marker)
- Gene -[EXPRESSEDIN]-> Disease (SPOKE: expressed in disease)
- Gene -[ASSOCIATES]-> Disease (Wikidata: genetic association)
- Gene -> GO Process -> Disease (via biological process involvement)

Usage:
    from analysis import GeneDiseasePathFinder

    finder = GeneDiseasePathFinder(verbose=True)
    connections = finder.find_all_connections("SFRP2")

    # Or run as script:
    python -m analysis.gene_paths SFRP2
    python -m analysis.gene_paths --gene ACTA2 --verbose
"""

import argparse
import json
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict

from clients.sparql import SPARQLClient


# SPOKE-OKN endpoint
SPOKE_ENDPOINT = "https://frink.apps.renci.org/spoke-okn/sparql"


@dataclass
class GeneDiseaseConnection:
    """A connection between a gene and a disease."""
    gene_symbol: str
    disease_id: str
    disease_name: str
    path_type: str
    source: str
    intermediate: Optional[str] = None
    evidence: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gene": self.gene_symbol,
            "disease_id": self.disease_id,
            "disease_name": self.disease_name,
            "path_type": self.path_type,
            "source": self.source,
            "intermediate": self.intermediate,
            "evidence": self.evidence,
        }


class GeneDiseasePathFinder:
    """Find paths from genes to diseases across multiple knowledge graphs."""

    def __init__(self, verbose: bool = False):
        self.client = SPARQLClient(timeout=120)
        self.verbose = verbose

    def log(self, msg: str):
        if self.verbose:
            print(f"  [DEBUG] {msg}")

    def find_all_connections(self, gene_symbol: str) -> List[GeneDiseaseConnection]:
        """
        Find all connections from a gene to diseases across knowledge graphs.

        Args:
            gene_symbol: Gene symbol (e.g., "SFRP2")

        Returns:
            List of GeneDiseaseConnection objects
        """
        connections = []

        # 1. SPOKE direct connections
        spoke_conns = self._query_spoke_gene_disease(gene_symbol)
        connections.extend(spoke_conns)

        # 2. Wikidata connections (gene → disease associations)
        wikidata_conns = self._query_wikidata_gene_disease(gene_symbol)
        connections.extend(wikidata_conns)

        # 3. GO-based connections (gene → GO term → disease)
        go_conns = self._query_go_disease_paths(gene_symbol)
        connections.extend(go_conns)

        # 4. Shared pathway connections (gene → GO term → other gene → disease)
        shared_conns = self._query_shared_go_disease(gene_symbol)
        connections.extend(shared_conns)

        return connections

    def _query_spoke_gene_disease(self, gene_symbol: str) -> List[GeneDiseaseConnection]:
        """Query SPOKE-OKN for direct gene-disease relationships."""
        connections = []

        # Query for all gene-disease predicates
        # Note: SPOKE uses https://purl.org/okn/frink/kg/spoke/schema/ namespace
        query = f'''
        PREFIX biolink: <https://w3id.org/biolink/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX spoke: <https://purl.org/okn/frink/kg/spoke/schema/>

        SELECT ?gene ?predicate ?disease
        WHERE {{
            ?gene a biolink:Gene ;
                  rdfs:label "{gene_symbol}" .

            # Get all disease-related predicates
            VALUES ?predicate {{
                spoke:MARKER_POS_GmpD
                spoke:MARKER_NEG_GmnD
                spoke:EXPRESSEDIN_GeiD
            }}
            ?gene ?predicate ?disease .
        }}
        '''

        self.log(f"Querying SPOKE for {gene_symbol}...")

        try:
            result = self.client.query(query, endpoint_url=SPOKE_ENDPOINT)
            self.log(f"Found {len(result)} SPOKE connections")

            for r in result:
                pred = r.get('predicate', {}).get('value', '')
                disease_uri = r.get('disease', {}).get('value', '')

                # Map predicate to path type
                if 'MARKER_POS' in pred:
                    path_type = "positive_marker"
                    evidence = "Gene is a positive marker for disease"
                elif 'MARKER_NEG' in pred:
                    path_type = "negative_marker"
                    evidence = "Gene is a negative marker for disease"
                elif 'EXPRESSEDIN' in pred:
                    path_type = "expressed_in"
                    evidence = "Gene is differentially expressed in disease"
                else:
                    path_type = "associated"
                    evidence = None

                # Get disease label from SPOKE or lookup
                disease_id = disease_uri.split('/')[-1]
                disease_name = self._get_disease_label(disease_uri)

                connections.append(GeneDiseaseConnection(
                    gene_symbol=gene_symbol,
                    disease_id=disease_id,
                    disease_name=disease_name,
                    path_type=path_type,
                    source="SPOKE-OKN",
                    evidence=evidence,
                ))

        except Exception as e:
            self.log(f"SPOKE query error: {e}")

        return connections

    def _get_disease_label(self, disease_uri: str) -> str:
        """Get disease label from SPOKE or Ubergraph."""
        # First try SPOKE
        query = f'''
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?label WHERE {{
            <{disease_uri}> rdfs:label ?label .
        }}
        '''
        try:
            result = self.client.query(query, endpoint_url=SPOKE_ENDPOINT)
            if result:
                return result[0].get('label', {}).get('value', disease_uri.split('/')[-1])
        except:
            pass

        # Try Ubergraph for DOID/MONDO
        if 'DOID' in disease_uri or 'MONDO' in disease_uri:
            try:
                result = self.client.query(query, endpoint='ubergraph')
                if result:
                    return result[0].get('label', {}).get('value', disease_uri.split('/')[-1])
            except:
                pass

        return disease_uri.split('/')[-1]

    def _query_wikidata_gene_disease(self, gene_symbol: str) -> List[GeneDiseaseConnection]:
        """Query Wikidata for gene-disease associations."""
        connections = []

        query = f'''
        PREFIX wdt: <http://www.wikidata.org/prop/direct/>
        PREFIX wd: <http://www.wikidata.org/entity/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?disease ?diseaseLabel ?doid ?mondo
        WHERE {{
            # Find the gene
            ?gene wdt:P353 "{gene_symbol}" ;
                  wdt:P703 wd:Q15978631 .  # Found in Homo sapiens

            # Gene associated with disease (P2293)
            ?gene wdt:P2293 ?disease .

            # Get disease label and IDs
            ?disease rdfs:label ?diseaseLabel .
            FILTER(LANG(?diseaseLabel) = "en")

            OPTIONAL {{ ?disease wdt:P699 ?doid . }}   # DOID
            OPTIONAL {{ ?disease wdt:P5270 ?mondo . }} # MONDO
        }}
        '''

        self.log(f"Querying Wikidata for {gene_symbol} disease associations...")

        try:
            result = self.client.query(query, endpoint='wikidata')
            self.log(f"Found {len(result)} Wikidata disease associations")

            for r in result:
                disease_label = r.get('diseaseLabel', {}).get('value', 'Unknown')
                doid = r.get('doid', {}).get('value', '')
                mondo = r.get('mondo', {}).get('value', '')
                disease_id = doid or mondo or r.get('disease', {}).get('value', '').split('/')[-1]

                connections.append(GeneDiseaseConnection(
                    gene_symbol=gene_symbol,
                    disease_id=disease_id,
                    disease_name=disease_label,
                    path_type="genetic_association",
                    source="Wikidata",
                    evidence="Gene genetically associated with disease",
                ))

        except Exception as e:
            self.log(f"Wikidata gene-disease query error: {e}")

        return connections

    def _query_go_disease_paths(self, gene_symbol: str) -> List[GeneDiseaseConnection]:
        """Find paths from gene to disease via GO terms."""
        connections = []

        # Step 1: Get GO terms for the gene's protein from Wikidata
        go_query = f'''
        PREFIX wdt: <http://www.wikidata.org/prop/direct/>
        PREFIX wd: <http://www.wikidata.org/entity/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?goId ?goLabel
        WHERE {{
            ?gene wdt:P353 "{gene_symbol}" ;
                  wdt:P703 wd:Q15978631 ;
                  wdt:P688 ?protein .  # encodes protein

            ?protein wdt:P680|wdt:P681|wdt:P682 ?goTerm .  # molecular function, cellular component, biological process
            ?goTerm wdt:P686 ?goId .
            ?goTerm rdfs:label ?goLabel .
            FILTER(LANG(?goLabel) = "en")
        }}
        '''

        self.log(f"Querying Wikidata for {gene_symbol} GO terms...")

        try:
            go_result = self.client.query(go_query, endpoint='wikidata')
            self.log(f"Found {len(go_result)} GO terms")

            if not go_result:
                return connections

            # Step 2: For each GO term, find related diseases in Ubergraph
            go_terms = [(r.get('goId', {}).get('value', ''),
                        r.get('goLabel', {}).get('value', '')) for r in go_result]

            # Query Ubergraph for GO → Disease relationships
            # This uses the has_phenotype or other ontology relationships
            for go_id, go_label in go_terms[:20]:  # Limit to avoid timeout
                disease_conns = self._query_go_to_disease(gene_symbol, go_id, go_label)
                connections.extend(disease_conns)

        except Exception as e:
            self.log(f"GO terms query error: {e}")

        return connections

    def _query_go_to_disease(self, gene_symbol: str, go_id: str, go_label: str) -> List[GeneDiseaseConnection]:
        """Query Ubergraph for diseases related to a GO term."""
        connections = []

        # Convert GO:0001234 to GO_0001234 for Ubergraph
        go_uri_id = go_id.replace(":", "_")

        # Query for diseases that have this GO term as a phenotype or component
        query = f'''
        PREFIX obo: <http://purl.obolibrary.org/obo/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>

        SELECT DISTINCT ?disease ?diseaseLabel
        WHERE {{
            # GO term
            BIND(obo:{go_uri_id} AS ?goTerm)

            # Find diseases that have this GO term or its subclasses
            # via has_phenotype_affecting or similar
            {{
                ?disease rdfs:subClassOf* obo:MONDO_0000001 .  # Is a disease
                ?disease rdfs:subClassOf ?restriction .
                ?restriction owl:onProperty ?prop ;
                             owl:someValuesFrom ?goTerm .
            }}
            UNION
            {{
                # Alternative: diseases with GO-related phenotypes
                ?disease rdfs:subClassOf* obo:MONDO_0000001 .
                ?disease obo:RO_0004027 ?goTerm .  # has_phenotype_affecting
            }}

            ?disease rdfs:label ?diseaseLabel .
        }}
        LIMIT 20
        '''

        try:
            result = self.client.query(query, endpoint='ubergraph')

            for r in result:
                disease_label = r.get('diseaseLabel', {}).get('value', 'Unknown')
                disease_uri = r.get('disease', {}).get('value', '')
                disease_id = disease_uri.split('/')[-1]

                connections.append(GeneDiseaseConnection(
                    gene_symbol=gene_symbol,
                    disease_id=disease_id,
                    disease_name=disease_label,
                    path_type="go_pathway",
                    source="Ubergraph",
                    intermediate=f"{go_id}: {go_label}",
                    evidence=f"Gene involved in {go_label}, which is associated with disease",
                ))

        except Exception as e:
            self.log(f"GO→Disease query error for {go_id}: {e}")

        return connections

    def _query_shared_go_disease(self, gene_symbol: str) -> List[GeneDiseaseConnection]:
        """Find diseases via other genes that share GO terms."""
        connections = []

        # Find genes sharing GO terms with the target gene
        # and check their disease associations in SPOKE
        query = f'''
        PREFIX wdt: <http://www.wikidata.org/prop/direct/>
        PREFIX wd: <http://www.wikidata.org/entity/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?otherSymbol ?goId ?goLabel
        WHERE {{
            # Target gene's protein and GO terms
            ?gene wdt:P353 "{gene_symbol}" ;
                  wdt:P703 wd:Q15978631 ;
                  wdt:P688 ?protein .
            ?protein wdt:P680|wdt:P681|wdt:P682 ?goTerm .
            ?goTerm wdt:P686 ?goId .
            ?goTerm rdfs:label ?goLabel .
            FILTER(LANG(?goLabel) = "en")

            # Other genes with same GO term
            ?otherGene wdt:P353 ?otherSymbol ;
                       wdt:P703 wd:Q15978631 ;
                       wdt:P688 ?otherProtein .
            ?otherProtein wdt:P680|wdt:P681|wdt:P682 ?goTerm .

            FILTER(?otherSymbol != "{gene_symbol}")
        }}
        LIMIT 100
        '''

        self.log(f"Finding genes sharing GO terms with {gene_symbol}...")

        try:
            result = self.client.query(query, endpoint='wikidata')
            self.log(f"Found {len(result)} shared GO term relationships")

            # For each related gene, check SPOKE for disease associations
            related_genes = {}
            for r in result:
                other = r.get('otherSymbol', {}).get('value', '')
                go_id = r.get('goId', {}).get('value', '')
                go_label = r.get('goLabel', {}).get('value', '')
                if other not in related_genes:
                    related_genes[other] = []
                related_genes[other].append((go_id, go_label))

            # Query SPOKE for disease associations of related genes
            if related_genes:
                gene_list = list(related_genes.keys())[:50]  # Limit to avoid timeout
                values_str = ' '.join(f'"{g}"' for g in gene_list)

                spoke_query = f'''
                PREFIX biolink: <https://w3id.org/biolink/vocab/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX spoke: <https://purl.org/okn/frink/kg/spoke/schema/>

                SELECT ?geneLabel ?disease
                WHERE {{
                    VALUES ?geneLabel {{ {values_str} }}
                    ?gene a biolink:Gene ;
                          rdfs:label ?geneLabel .
                    ?gene spoke:MARKER_POS_GmpD|spoke:EXPRESSEDIN_GeiD ?disease .
                }}
                '''

                spoke_result = self.client.query(spoke_query, endpoint_url=SPOKE_ENDPOINT)
                self.log(f"Found {len(spoke_result)} related gene-disease connections")

                for r in spoke_result:
                    other_gene = r.get('geneLabel', {}).get('value', '')
                    disease_uri = r.get('disease', {}).get('value', '')
                    disease_id = disease_uri.split('/')[-1]
                    disease_name = self._get_disease_label(disease_uri)

                    # Get the shared GO term
                    go_terms = related_genes.get(other_gene, [])
                    intermediate = f"{other_gene} (shares: {go_terms[0][0]})" if go_terms else other_gene

                    connections.append(GeneDiseaseConnection(
                        gene_symbol=gene_symbol,
                        disease_id=disease_id,
                        disease_name=disease_name,
                        path_type="shared_pathway",
                        source="SPOKE+Wikidata",
                        intermediate=intermediate,
                        evidence=f"Gene shares GO term with {other_gene}, which is associated with disease",
                    ))

        except Exception as e:
            self.log(f"Shared GO term query error: {e}")

        return connections

    def summarize_connections(self, connections: List[GeneDiseaseConnection]) -> Dict[str, Any]:
        """Summarize connections by path type and source."""
        summary = {
            "total_connections": len(connections),
            "by_source": defaultdict(list),
            "by_path_type": defaultdict(list),
            "unique_diseases": set(),
        }

        for conn in connections:
            summary["by_source"][conn.source].append(conn.disease_name)
            summary["by_path_type"][conn.path_type].append(conn.disease_name)
            summary["unique_diseases"].add(conn.disease_name)

        summary["unique_diseases"] = list(summary["unique_diseases"])
        summary["by_source"] = dict(summary["by_source"])
        summary["by_path_type"] = dict(summary["by_path_type"])

        return summary


def main():
    parser = argparse.ArgumentParser(
        description="Find gene-disease connections across knowledge graphs"
    )
    parser.add_argument("gene", nargs="?", help="Gene symbol (e.g., SFRP2)")
    parser.add_argument("--gene", "-g", dest="gene_arg", help="Gene symbol (alternative)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument("--html", help="Output interactive HTML visualization")

    args = parser.parse_args()

    gene_symbol = args.gene or args.gene_arg
    if not gene_symbol:
        parser.error("Gene symbol is required")

    gene_symbol = gene_symbol.upper()

    print("=" * 70)
    print(f"GENE-DISEASE PATH FINDER: {gene_symbol}")
    print("=" * 70)
    print()
    print("Sources:")
    print("  - SPOKE-OKN (frink.apps.renci.org/spoke-okn)")
    print("  - Wikidata (query.wikidata.org)")
    print("  - Ubergraph (ubergraph.apps.renci.org)")
    print()

    finder = GeneDiseasePathFinder(verbose=args.verbose)
    connections = finder.find_all_connections(gene_symbol)

    if not connections:
        print(f"No connections found for {gene_symbol}")
        return

    # Group and display results
    print("-" * 70)
    print(f"CONNECTIONS FOUND: {len(connections)}")
    print("-" * 70)
    print()

    # Group by source
    by_source = defaultdict(list)
    for conn in connections:
        by_source[conn.source].append(conn)

    for source, source_conns in by_source.items():
        print(f"## {source} ({len(source_conns)} connections)")
        print()

        # Group by path type within source
        by_type = defaultdict(list)
        for conn in source_conns:
            by_type[conn.path_type].append(conn)

        for path_type, type_conns in by_type.items():
            print(f"  ### {path_type.replace('_', ' ').title()} ({len(type_conns)})")

            for conn in type_conns[:10]:  # Show first 10
                intermediate = f" via [{conn.intermediate}]" if conn.intermediate else ""
                print(f"    - {conn.disease_name} ({conn.disease_id}){intermediate}")

            if len(type_conns) > 10:
                print(f"    ... and {len(type_conns) - 10} more")
            print()

    # Summary
    summary = finder.summarize_connections(connections)

    print("-" * 70)
    print("SUMMARY")
    print("-" * 70)
    print(f"Total connections: {summary['total_connections']}")
    print(f"Unique diseases: {len(summary['unique_diseases'])}")
    print()
    print("By source:")
    for source, diseases in summary["by_source"].items():
        print(f"  - {source}: {len(diseases)} connections")
    print()
    print("By path type:")
    for path_type, diseases in summary["by_path_type"].items():
        print(f"  - {path_type}: {len(diseases)} connections")

    # Output to file
    if args.output:
        output_data = {
            "gene": gene_symbol,
            "total_connections": len(connections),
            "connections": [c.to_dict() for c in connections],
            "summary": {
                "unique_diseases": summary["unique_diseases"],
                "by_source": {k: len(v) for k, v in summary["by_source"].items()},
                "by_path_type": {k: len(v) for k, v in summary["by_path_type"].items()},
            }
        }
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults saved to: {args.output}")

    # Generate interactive visualization
    if args.html:
        try:
            from analysis.visualization import PlotlyVisualizer

            viz = PlotlyVisualizer()
            conn_dicts = [c.to_dict() for c in connections]

            # Create network graph (returns HTML string for vis.js)
            html_content = viz.gene_disease_network(
                conn_dicts,
                title=f"{gene_symbol} Disease Connections",
                gene_symbol=gene_symbol,
            )
            with open(args.html, "w") as f:
                f.write(html_content)
            print(f"\nNetwork visualization saved to: {args.html}")

            # Also create source summary if multiple sources
            if len(summary["by_source"]) > 1:
                summary_file = args.html.replace(".html", "_sources.html")
                fig2 = viz.source_summary(conn_dicts, title=f"{gene_symbol} Connections by Source")
                viz.save_html(fig2, summary_file)
                print(f"Source summary saved to: {summary_file}")

        except ImportError:
            print("\nWarning: plotly not installed. Skipping visualization.")
            print("Install with: pip install plotly")


if __name__ == "__main__":
    main()
