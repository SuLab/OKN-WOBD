"""
Data source clients for biomedical queries.

Provides unified interfaces for:
- SPARQL endpoints (FRINK, Wikidata, local Fuseki)
- NIAID Data Ecosystem Discovery Portal
- ARCHS4 bulk RNA-seq (HDF5)
- CellxGene Census single-cell RNA-seq
"""
from clients.sparql import SPARQLClient, QueryResult, COMMON_PREFIXES, GXA_PREFIXES, GXAQueries
from clients.niaid import NIAIDClient, SearchResult, COMMON_SPECIES, COMMON_DISEASES, COMMON_CATALOGS
from clients.archs4 import ARCHS4Client, ARCHS4DataFile
from clients.archs4_index import ARCHS4MetadataIndex
from clients.cellxgene import CellxGeneClient, ExpressionStats, ConditionComparison
from clients.http_utils import create_session
from clients.ontology import DiseaseOntologyClient, MondoResolution, OntologyExpansion
from clients.nde_geo import NDEGeoDiscovery, GEOStudyMatch, NDEGeoDiscoveryResult
