#!/usr/bin/env python3
"""
Microbial Terpenoid Biosynthesis Analyzer

Answers the question: "For microbial genes involved in terpene biosynthesis,
what are some experiments that show biological contexts where those genes
are upregulated?"

This script focuses on MANUFACTURING use cases (not infectious disease),
identifying datasets where microbes are studied for terpenoid production.

Workflow:
=========
1. KNOWLEDGE GRAPH LAYER (Ubergraph + Wikidata)
   - Get GO terms for terpenoid/isoprenoid biosynthesis
   - Get bacterial/fungal genes annotated to these GO terms
   - Include MEP pathway genes (DXS, DXR, IspD, IspE, IspF, IspG, IspH)

2. NDE DISCOVERY LAYER (NIAID Data Ecosystem)
   - Search for datasets related to these genes/pathways
   - Filter for manufacturing-relevant organisms (E. coli, yeast, Streptomyces)
   - Identify transcriptomics/expression datasets

3. LLM SUMMARY LAYER (Claude)
   - Generate natural language summary of findings

Usage:
    python microbial_terpenoid_analyzer.py --output results.json
    python microbial_terpenoid_analyzer.py --organism yeast --output yeast_results.json
    python microbial_terpenoid_analyzer.py --pathway MEP --output mep_results.json
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional, Set

# Local imports
from sparql_client import SPARQLClient
from niaid_client import NIAIDClient

# GO terms for terpenoid biosynthesis
TERPENOID_GO_TERMS = {
    "GO:0016114": "terpenoid biosynthetic process",
    "GO:0006721": "terpenoid metabolic process",
    "GO:0019287": "isopentenyl diphosphate biosynthetic process, mevalonate pathway",
    "GO:0019288": "isopentenyl diphosphate biosynthetic process, MEP pathway",
    "GO:0050992": "dimethylallyl diphosphate biosynthetic process",
    "GO:0046246": "terpene biosynthetic process",
    "GO:0008299": "isoprenoid biosynthetic process",
}

# MEP pathway genes (found in bacteria)
MEP_PATHWAY_GENES = {
    "dxs": "1-deoxy-D-xylulose-5-phosphate synthase",
    "dxr": "1-deoxy-D-xylulose 5-phosphate reductoisomerase (IspC)",
    "ispD": "4-diphosphocytidyl-2-C-methyl-D-erythritol synthase",
    "ispE": "4-diphosphocytidyl-2-C-methyl-D-erythritol kinase",
    "ispF": "2-C-methyl-D-erythritol 2,4-cyclodiphosphate synthase",
    "ispG": "4-hydroxy-3-methylbut-2-en-1-yl diphosphate synthase",
    "ispH": "4-hydroxy-3-methylbut-2-enyl diphosphate reductase",
}

# Mevalonate pathway genes (found in fungi/yeast)
MVA_PATHWAY_GENES = {
    "ERG10": "acetyl-CoA C-acetyltransferase",
    "ERG13": "hydroxymethylglutaryl-CoA synthase",
    "HMG1": "HMG-CoA reductase 1",
    "HMG2": "HMG-CoA reductase 2",
    "ERG12": "mevalonate kinase",
    "ERG8": "phosphomevalonate kinase",
    "MVD1": "mevalonate diphosphate decarboxylase",
    "IDI1": "isopentenyl-diphosphate delta-isomerase",
    "ERG20": "farnesyl diphosphate synthase",
}

# Manufacturing-relevant organisms
MANUFACTURING_ORGANISMS = {
    "bacteria": {
        "E. coli": ["Escherichia coli", "562"],
        "Bacillus subtilis": ["Bacillus subtilis", "1423"],
        "Corynebacterium": ["Corynebacterium glutamicum", "1718"],
        "Streptomyces": ["Streptomyces", "1883"],
        "Pseudomonas": ["Pseudomonas putida", "303"],
    },
    "yeast": {
        "S. cerevisiae": ["Saccharomyces cerevisiae", "4932"],
        "Yarrowia": ["Yarrowia lipolytica", "4952"],
        "Pichia": ["Pichia pastoris", "4922"],
    },
    "fungi": {
        "Aspergillus": ["Aspergillus", "5052"],
        "Trichoderma": ["Trichoderma", "5543"],
    }
}


@dataclass
class GeneInfo:
    """Information about a terpenoid biosynthesis gene."""
    symbol: str
    name: str
    pathway: str  # MEP or MVA
    organism_type: str  # bacteria, yeast, fungi
    go_terms: List[str] = field(default_factory=list)
    wikidata_id: Optional[str] = None


@dataclass
class DatasetInfo:
    """Information about a relevant dataset."""
    name: str
    description: str
    url: str
    source: str  # Data catalog name
    species: List[str]
    data_type: str  # transcriptome, proteome, metabolome, etc.
    relevance_score: float  # How relevant to the query
    genes_mentioned: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Complete analysis result."""
    query: Dict[str, Any]
    timestamp: str
    layer1_knowledge: Dict[str, Any]
    layer2_datasets: Dict[str, Any]
    summary: str = ""


class MicrobialTerpenoidAnalyzer:
    """Analyzer for microbial terpenoid biosynthesis experiments."""

    def __init__(self, cache_dir: Optional[str] = None):
        self.niaid_client = NIAIDClient()
        self.sparql_client = SPARQLClient()
        self.cache_dir = cache_dir or os.environ.get("DATA_DIR", ".")

    def get_terpenoid_go_hierarchy(self) -> Dict[str, Any]:
        """Get GO term hierarchy for terpenoid biosynthesis from Ubergraph."""
        print("\n" + "="*60)
        print("LAYER 1: Knowledge Graph - GO Term Hierarchy")
        print("="*60)

        # Query Ubergraph for terpenoid biosynthesis GO terms
        query = """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX obo: <http://purl.obolibrary.org/obo/>

        SELECT DISTINCT ?go_term ?label WHERE {
            VALUES ?parent {
                obo:GO_0016114  # terpenoid biosynthetic process
                obo:GO_0008299  # isoprenoid biosynthetic process
                obo:GO_0019288  # MEP pathway
                obo:GO_0019287  # mevalonate pathway
            }
            ?go_term rdfs:subClassOf* ?parent .
            ?go_term rdfs:label ?label .
            FILTER(STRSTARTS(STR(?go_term), "http://purl.obolibrary.org/obo/GO_"))
        }
        """

        try:
            results = self.sparql_client.query(
                query,
                endpoint='https://ubergraph.apps.renci.org/sparql'
            )

            go_terms = {}
            for r in results:
                go_id = r['go_term']['value'].replace('http://purl.obolibrary.org/obo/GO_', 'GO:')
                label = r['label']['value']
                go_terms[go_id] = label

            print(f"Found {len(go_terms)} GO terms in terpenoid biosynthesis hierarchy")
            return go_terms

        except Exception as e:
            print(f"Warning: Could not query Ubergraph: {e}")
            return TERPENOID_GO_TERMS.copy()

    def get_microbial_genes_from_wikidata(self) -> List[GeneInfo]:
        """Get bacterial/fungal terpenoid biosynthesis genes from Wikidata."""
        print("\nQuerying Wikidata for microbial terpenoid genes...")

        # Query for genes annotated to terpenoid biosynthesis GO terms
        query = """
        SELECT DISTINCT ?gene ?geneLabel ?taxonLabel ?go_term WHERE {
            ?gene wdt:P31 wd:Q7187 .  # instance of gene
            ?gene wdt:P703 ?taxon .   # found in taxon
            ?gene wdt:P682 ?go .      # biological process

            # Filter for bacteria or fungi
            { ?taxon wdt:P171* wd:Q10876 }  # subclass of bacteria
            UNION
            { ?taxon wdt:P171* wd:Q764 }    # subclass of fungi

            # Get GO term ID
            ?go wdt:P686 ?go_term .

            # Filter for terpenoid-related GO terms
            FILTER(
                ?go_term IN ("GO:0016114", "GO:0008299", "GO:0019288", "GO:0019287",
                            "GO:0006721", "GO:0046246", "GO:0050992")
            )

            SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 200
        """

        genes = []

        try:
            results = self.sparql_client.query(
                query,
                endpoint='https://query.wikidata.org/sparql'
            )

            for r in results:
                gene = GeneInfo(
                    symbol=r.get('geneLabel', {}).get('value', 'Unknown'),
                    name=r.get('geneLabel', {}).get('value', 'Unknown'),
                    pathway="terpenoid",
                    organism_type=r.get('taxonLabel', {}).get('value', 'Unknown'),
                    go_terms=[r.get('go_term', {}).get('value', '')],
                    wikidata_id=r.get('gene', {}).get('value', '').split('/')[-1]
                )
                genes.append(gene)

            print(f"Found {len(genes)} genes from Wikidata")

        except Exception as e:
            print(f"Warning: Wikidata query failed: {e}")

        # Add known MEP pathway genes
        for symbol, name in MEP_PATHWAY_GENES.items():
            genes.append(GeneInfo(
                symbol=symbol,
                name=name,
                pathway="MEP",
                organism_type="bacteria",
                go_terms=["GO:0019288"]
            ))

        # Add known MVA pathway genes
        for symbol, name in MVA_PATHWAY_GENES.items():
            genes.append(GeneInfo(
                symbol=symbol,
                name=name,
                pathway="MVA",
                organism_type="yeast",
                go_terms=["GO:0019287"]
            ))

        print(f"Total genes (including known pathway genes): {len(genes)}")
        return genes

    def search_nde_datasets(
        self,
        organism_filter: Optional[str] = None,
        pathway_filter: Optional[str] = None,
        max_results: int = 50
    ) -> List[DatasetInfo]:
        """Search NDE for relevant terpenoid biosynthesis datasets."""
        print("\n" + "="*60)
        print("LAYER 2: NDE Discovery - Expression/Transcriptomics Datasets")
        print("="*60)

        datasets = []
        seen_urls = set()

        # Build search queries based on filters
        queries = []

        if pathway_filter and pathway_filter.upper() == "MEP":
            queries.extend([
                '"MEP pathway" AND (expression OR transcriptome OR RNA-seq)',
                'methylerythritol AND (bacteria OR microbial) AND biosynthesis',
                '(dxs OR dxr OR ispC OR ispD OR ispE OR ispF OR ispG OR ispH) AND expression',
            ])
        elif pathway_filter and pathway_filter.upper() == "MVA":
            queries.extend([
                'mevalonate AND (yeast OR Saccharomyces) AND expression',
                '(HMG1 OR ERG20 OR IDI1) AND terpenoid AND yeast',
            ])
        else:
            queries.extend([
                'terpenoid AND (expression OR transcriptome OR RNA-seq) AND (microbial OR bacteria OR yeast OR fungi)',
                'terpenoid AND biosynthesis AND (E. coli OR Saccharomyces OR Yarrowia)',
                '"terpene synthase" AND (expression OR transcriptome)',
                'isoprenoid AND production AND (microbial OR fermentation)',
                'terpenoid AND "genome mining"',
            ])

        if organism_filter:
            organism_map = {
                "ecoli": "Escherichia coli",
                "e. coli": "Escherichia coli",
                "yeast": "(Saccharomyces OR Yarrowia OR yeast)",
                "streptomyces": "Streptomyces",
                "bacteria": "(bacteria OR E. coli OR Bacillus)",
                "fungi": "(fungi OR fungal OR Aspergillus)",
            }
            org_term = organism_map.get(organism_filter.lower(), organism_filter)
            queries = [f"({q}) AND {org_term}" for q in queries]

        for query in queries:
            print(f"\nSearching: {query[:60]}...")

            try:
                result = self.niaid_client.search(query, size=max_results // len(queries))
                print(f"  Found {result.total} total matches")

                for hit in result.hits:
                    url = hit.get('url', '')
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    # Extract species
                    species_list = []
                    species = hit.get('species', [])
                    if isinstance(species, list):
                        species_list = [s.get('name', '') for s in species if isinstance(s, dict)]
                    elif isinstance(species, dict):
                        species_list = [species.get('name', '')]

                    # Get catalog name
                    catalogs = hit.get('includedInDataCatalog', [])
                    source = ''
                    if catalogs:
                        if isinstance(catalogs, list) and catalogs:
                            source = catalogs[0].get('name', '') if isinstance(catalogs[0], dict) else ''
                        elif isinstance(catalogs, dict):
                            source = catalogs.get('name', '')

                    # Determine data type from description/keywords
                    desc = hit.get('description', '').lower()
                    name = hit.get('name', '').lower()
                    keywords = hit.get('keywords', [])
                    if isinstance(keywords, str):
                        keywords = [keywords]

                    data_type = "unknown"
                    if any(t in desc or t in name for t in ['rna-seq', 'rnaseq', 'transcriptom']):
                        data_type = "transcriptome"
                    elif any(t in desc or t in name for t in ['proteom', 'mass spec']):
                        data_type = "proteome"
                    elif any(t in desc or t in name for t in ['metabolom', 'metabolite']):
                        data_type = "metabolome"
                    elif any(t in desc or t in name for t in ['genome', 'genomic']):
                        data_type = "genome"
                    elif any(t in desc or t in name for t in ['crystal', 'structure', 'pdb']):
                        data_type = "structure"

                    # Calculate relevance score
                    relevance = 0.0
                    relevance_terms = [
                        ('expression', 0.3), ('transcriptom', 0.3), ('rna-seq', 0.3),
                        ('upregulat', 0.2), ('downregulat', 0.2), ('differential', 0.2),
                        ('biosynthesis', 0.15), ('production', 0.15), ('pathway', 0.1),
                        ('terpene', 0.1), ('terpenoid', 0.1), ('isoprenoid', 0.1),
                    ]
                    for term, score in relevance_terms:
                        if term in desc or term in name:
                            relevance += score

                    # Identify mentioned genes
                    genes_mentioned = []
                    all_genes = list(MEP_PATHWAY_GENES.keys()) + list(MVA_PATHWAY_GENES.keys())
                    for gene in all_genes:
                        if gene.lower() in desc or gene.lower() in name:
                            genes_mentioned.append(gene)

                    dataset = DatasetInfo(
                        name=hit.get('name', 'Untitled')[:200],
                        description=hit.get('description', '')[:500],
                        url=url,
                        source=source,
                        species=species_list,
                        data_type=data_type,
                        relevance_score=min(relevance, 1.0),
                        genes_mentioned=genes_mentioned,
                        keywords=keywords[:10] if keywords else []
                    )
                    datasets.append(dataset)

            except Exception as e:
                print(f"  Error: {e}")

        # Sort by relevance
        datasets.sort(key=lambda x: x.relevance_score, reverse=True)
        print(f"\nTotal unique datasets found: {len(datasets)}")

        return datasets[:max_results]

    def categorize_datasets(self, datasets: List[DatasetInfo]) -> Dict[str, List[DatasetInfo]]:
        """Categorize datasets by type and organism."""
        categories = {
            "transcriptomics": [],
            "proteomics": [],
            "structural": [],
            "metabolomics": [],
            "genomics": [],
            "other": [],
            "by_organism": {
                "yeast": [],
                "bacteria": [],
                "fungi": [],
                "other": [],
            }
        }

        for ds in datasets:
            # By data type
            if ds.data_type == "transcriptome":
                categories["transcriptomics"].append(ds)
            elif ds.data_type == "proteome":
                categories["proteomics"].append(ds)
            elif ds.data_type == "structure":
                categories["structural"].append(ds)
            elif ds.data_type == "metabolome":
                categories["metabolomics"].append(ds)
            elif ds.data_type == "genome":
                categories["genomics"].append(ds)
            else:
                categories["other"].append(ds)

            # By organism
            species_str = ' '.join(ds.species).lower()
            desc_lower = ds.description.lower()
            name_lower = ds.name.lower()

            if any(t in species_str or t in desc_lower or t in name_lower
                   for t in ['saccharomyces', 'yarrowia', 'pichia', 'yeast']):
                categories["by_organism"]["yeast"].append(ds)
            elif any(t in species_str or t in desc_lower or t in name_lower
                     for t in ['e. coli', 'escherichia', 'bacillus', 'streptomyces', 'bacteria']):
                categories["by_organism"]["bacteria"].append(ds)
            elif any(t in species_str or t in desc_lower or t in name_lower
                     for t in ['fungi', 'fungal', 'aspergillus', 'trichoderma']):
                categories["by_organism"]["fungi"].append(ds)
            else:
                categories["by_organism"]["other"].append(ds)

        return categories

    def generate_summary(self, result: AnalysisResult) -> str:
        """Generate a natural language summary of findings."""
        lines = []
        lines.append("SUMMARY: Microbial Terpenoid Biosynthesis Datasets")
        lines.append("=" * 50)
        lines.append("")

        # Knowledge layer summary
        kg = result.layer1_knowledge
        lines.append(f"Knowledge Graph Layer:")
        lines.append(f"  - {kg.get('n_go_terms', 0)} GO terms in terpenoid biosynthesis hierarchy")
        lines.append(f"  - {kg.get('n_genes', 0)} genes identified (MEP + MVA pathways)")
        lines.append("")

        # Dataset summary
        ds = result.layer2_datasets
        lines.append(f"NDE Dataset Discovery:")
        lines.append(f"  - {ds.get('total_datasets', 0)} relevant datasets found")
        lines.append("")

        categories = ds.get('categories', {})

        # By data type
        lines.append("Datasets by Type:")
        for dtype in ['transcriptomics', 'proteomics', 'metabolomics', 'structural', 'genomics']:
            count = len(categories.get(dtype, []))
            if count > 0:
                lines.append(f"  - {dtype.capitalize()}: {count}")
        lines.append("")

        # By organism
        lines.append("Datasets by Organism:")
        for org in ['yeast', 'bacteria', 'fungi']:
            count = len(categories.get('by_organism', {}).get(org, []))
            if count > 0:
                lines.append(f"  - {org.capitalize()}: {count}")
        lines.append("")

        # Top datasets for expression analysis
        lines.append("Top Expression/Transcriptomics Datasets:")
        transcriptomics = categories.get('transcriptomics', [])[:5]
        if transcriptomics:
            for i, ds_dict in enumerate(transcriptomics, 1):
                # Handle both DatasetInfo objects and dicts
                if isinstance(ds_dict, dict):
                    name = ds_dict.get('name', 'Unknown')
                    species = ds_dict.get('species', [])
                    url = ds_dict.get('url', '')
                else:
                    name = ds_dict.name
                    species = ds_dict.species
                    url = ds_dict.url
                lines.append(f"  {i}. {name[:70]}")
                if species:
                    lines.append(f"     Species: {', '.join(species[:3])}")
                lines.append(f"     URL: {url}")
        else:
            lines.append("  No transcriptomics datasets found")

        lines.append("")
        lines.append("These datasets can be analyzed to identify conditions where")
        lines.append("terpenoid biosynthesis genes are upregulated in manufacturing")
        lines.append("organisms like E. coli, S. cerevisiae, and Yarrowia.")

        return "\n".join(lines)

    def analyze(
        self,
        organism_filter: Optional[str] = None,
        pathway_filter: Optional[str] = None,
        max_datasets: int = 50,
    ) -> AnalysisResult:
        """Run complete analysis."""
        timestamp = datetime.now().isoformat()

        # Layer 1: Knowledge Graph
        go_terms = self.get_terpenoid_go_hierarchy()
        genes = self.get_microbial_genes_from_wikidata()

        # Layer 2: NDE Discovery
        datasets = self.search_nde_datasets(
            organism_filter=organism_filter,
            pathway_filter=pathway_filter,
            max_results=max_datasets
        )

        categories = self.categorize_datasets(datasets)

        # Build result
        result = AnalysisResult(
            query={
                "type": "microbial_terpenoid_biosynthesis",
                "organism_filter": organism_filter,
                "pathway_filter": pathway_filter,
                "timestamp": timestamp,
            },
            timestamp=timestamp,
            layer1_knowledge={
                "n_go_terms": len(go_terms),
                "go_terms": go_terms,
                "n_genes": len(genes),
                "mep_pathway_genes": list(MEP_PATHWAY_GENES.keys()),
                "mva_pathway_genes": list(MVA_PATHWAY_GENES.keys()),
                "sample_genes": [asdict(g) for g in genes[:10]],
            },
            layer2_datasets={
                "total_datasets": len(datasets),
                "datasets": [asdict(d) for d in datasets],
                "categories": {
                    k: [asdict(d) for d in v] if isinstance(v, list) else {
                        k2: [asdict(d) for d in v2] for k2, v2 in v.items()
                    }
                    for k, v in categories.items()
                },
            },
        )

        result.summary = self.generate_summary(result)

        return result

    def print_report(self, result: AnalysisResult):
        """Print a formatted report to console."""
        print("\n" + "="*70)
        print("MICROBIAL TERPENOID BIOSYNTHESIS ANALYSIS REPORT")
        print("="*70)
        print(f"Timestamp: {result.timestamp}")
        print(f"Query: {result.query}")
        print()
        print(result.summary)
        print()

        # Detailed dataset listing
        print("\n" + "-"*70)
        print("DETAILED DATASET LISTING")
        print("-"*70)

        datasets = [DatasetInfo(**d) for d in result.layer2_datasets['datasets'][:20]]

        for i, ds in enumerate(datasets, 1):
            print(f"\n{i}. {ds.name}")
            print(f"   Type: {ds.data_type}")
            print(f"   Source: {ds.source}")
            if ds.species:
                print(f"   Species: {', '.join(ds.species[:3])}")
            if ds.genes_mentioned:
                print(f"   Genes: {', '.join(ds.genes_mentioned)}")
            print(f"   Relevance: {ds.relevance_score:.2f}")
            print(f"   URL: {ds.url}")
            if ds.description:
                desc_preview = ds.description[:150] + "..." if len(ds.description) > 150 else ds.description
                print(f"   Description: {desc_preview}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze microbial terpenoid biosynthesis experiments"
    )
    parser.add_argument(
        "--organism", "-o",
        help="Filter by organism (e.g., 'yeast', 'ecoli', 'streptomyces', 'bacteria', 'fungi')"
    )
    parser.add_argument(
        "--pathway", "-p",
        choices=["MEP", "MVA", "mep", "mva"],
        help="Filter by pathway (MEP for bacteria, MVA for yeast/fungi)"
    )
    parser.add_argument(
        "--max-datasets", "-m",
        type=int,
        default=50,
        help="Maximum number of datasets to retrieve"
    )
    parser.add_argument(
        "--output", "-f",
        help="Output JSON file"
    )

    args = parser.parse_args()

    analyzer = MicrobialTerpenoidAnalyzer()

    result = analyzer.analyze(
        organism_filter=args.organism,
        pathway_filter=args.pathway.upper() if args.pathway else None,
        max_datasets=args.max_datasets,
    )

    # Print report
    analyzer.print_report(result)

    # Save to file
    if args.output:
        output_data = {
            "query": result.query,
            "timestamp": result.timestamp,
            "layer1_knowledge": result.layer1_knowledge,
            "layer2_datasets": result.layer2_datasets,
            "summary": result.summary,
        }

        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
