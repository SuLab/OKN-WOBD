// Registry graph data - auto-updated from OKN Registry
// This file is automatically updated when registry fetch succeeds
// Last updated: 2026-01-28T03:33:20.489Z
// Source: /Users/whetzel/git/SuLab/OKN-WOBD/web-v2/data/registry-graphs.json

import type { GraphInfo } from "@/types";

export interface RegistryGraphInfo extends GraphInfo {
  description?: string;
  title?: string;
}

// Initial/fallback graph list - updated automatically from registry
export const GRAPHS_DATA: RegistryGraphInfo[] = [
  { 
    shortname: "biobricks-aopwiki", 
    label: "BioBricks AOP-Wiki",    description: "BioBricks AOP-Wiki is an open knowledge graph for Adverse Outcome Pathways from the AOP-Wiki.",
    endpoint: "https://frink.apps.renci.org/biobricks-aopwiki/sparql",
  },
  { 
    shortname: "biobricks-ice", 
    label: "BioBricks ICE",    description: "BioBricks ICE (Integrated Chemical Environment) is an open knowledge graph for cheminformatics and chemical safety data from EPA's CompTox database.",
    endpoint: "https://frink.apps.renci.org/biobricks-ice/sparql",
  },
  { 
    shortname: "biobricks-mesh", 
    label: "BioBricks MeSH",    description: "BioBricks MeSH is an open knowledge graph of Medical Subject Headings (MeSH) biomedical vocabulary.",
    endpoint: "https://frink.apps.renci.org/biobricks-mesh/sparql",
  },
  { 
    shortname: "biobricks-pubchem-annotations", 
    label: "BioBricks PubChem Annotations",    description: "BioBricks PubChem Annotations is an open knowledge graph of chemical annotations from PubChem.",
    endpoint: "https://frink.apps.renci.org/biobricks-pubchem-annotations/sparql",
  },
  { 
    shortname: "biobricks-tox21", 
    label: "BioBricks Tox21",    description: "BioBricks Tox21 is an open knowledge graph for Tox21 toxicology screening data.",
    endpoint: "https://frink.apps.renci.org/biobricks-tox21/sparql",
  },
  { 
    shortname: "biobricks-toxcast", 
    label: "BioBricks ToxCast",    description: "BioBricks ToxCast is an open knowledge graph for EPA ToxCast high-throughput screening data.",
    endpoint: "https://frink.apps.renci.org/biobricks-toxcast/sparql",
  },
  { 
    shortname: "biohealth", 
    label: "Bio-Health KG",    description: "Bio-Health KG is a dynamically-updated open knowledge network for health, integrating biomedical insights with social determinants of health.",
    endpoint: "https://frink.apps.renci.org/biohealth/sparql",
  },
  { 
    shortname: "climatemodelskg", 
    label: "Climate Models KG",    description: "Climate Models KG is a knowledge graph to support evaluation and development of climate models.",
    endpoint: "https://frink.apps.renci.org/climatemodelskg/sparql",
  },
  { 
    shortname: "dreamkg", 
    label: "DREAM-KG",    description: "Develop Dynamic, REsponsive, Adaptive, and Multifaceted Knowledge Graphs to Address Homelessness With Explainable AI",
    endpoint: "https://frink.apps.renci.org/dreamkg/sparql",
  },
  { 
    shortname: "fiokg", 
    label: "SAWGraph FRS KG",    description: "The FRS (Facility Registry Service) KG is the part of the SAWGraph project that stores data about facilities from EPA's Facility Registry service (FRS) together with their NAICS industry classification and the spatial location.",
    endpoint: "https://frink.apps.renci.org/fiokg/sparql",
  },
  { 
    shortname: "gene-expression-atlas-okn", 
    label: "Gene Expression Atlas",    description: "Selected studies from the Gene Expression Atlas (https://www.ebi.ac.uk/gxa/home).",
    endpoint: "https://frink.apps.renci.org/gene-expression-atlas-okn/sparql",
  },
  { 
    shortname: "geoconnex", 
    label: "GEOCONNEX",    description: "Geoconnex is an open, community-driven knowledge graph linking U.S. hydrologic features to enable seamless water data discovery, access, and collaborative monitoring.",
    endpoint: "https://frink.apps.renci.org/geoconnex/sparql",
  },
  { 
    shortname: "hydrologykg", 
    label: "SAWGraph Hydrology KG",    description: "The Hydrology KG is the part of the SAWGraph project that describes streams, waterbodies and wells and their locations.",
    endpoint: "https://frink.apps.renci.org/hydrologykg/sparql",
  },
  { 
    shortname: "identifier-mappings", 
    label: "ID Mappings",    description: "Mappings using standard RDF predicates between Wikidata entities and external identifiers represented as RDF IRIs",
    endpoint: "https://frink.apps.renci.org/identifier-mappings/sparql",
  },
  { 
    shortname: "nasa-gesdisc-kg", 
    label: "NASA-GESDISC-KG",    description: "The NASA Knowledge Graph Dataset is an expansive graph-based dataset designed to integrate and interconnect information about satellite datasets, scientific publications, instruments, platforms, projects, data centers, and science keywords. This knowledge graph is particularly focused on datasets managed by NASA's Distributed Active Archive Centers (DAACs), which are NASA's data repositories responsible for archiving and distributing scientific data. In addition to NASA DAACs, the graph includes datasets from 184 data providers worldwide, including various government agencies and academic institutions.",
    endpoint: "https://frink.apps.renci.org/nasa-gesdisc-kg/sparql",
  },
  { 
    shortname: "nde", 
    label: "NIAID Data Ecosystem KG",    description: "The nde (NIAID Data Ecosystem) KG contains infectious and immune-mediated disease datasets. These include datasets from NIAID-funded repositories as well as globally-relevant infectious and immune-mediated disease (IID) repositories from NIH and beyond. The datasets include -omics data, clinical data, epidemiological data, pathogen-host interaction data, flow cytometry, and imaging.",
    endpoint: "https://frink.apps.renci.org/nde/sparql",
  },
  { 
    shortname: "nikg", 
    label: "Neighborhood Information KG",    description: "Neighborhood Information KG (NIKG) is a knowledge graph warehouse for neighborhood information.",
    endpoint: "https://frink.apps.renci.org/nikg/sparql",
  },
  { 
    shortname: "prokn", 
    label: "Protein Knowledge Network",    description: "The Protein Knowledge Network (ProKN) integrates protein-centric data with the genomic-centric datasets of the Common Fund Data Ecosystem (CFDE), spanning heterogeneous biological data types across multiple domains to foster CFDE re-use and collaboration through enhanced connectivity and data integration, enabling new capabilities for functional genomics and systems-level understanding of disease mechanisms.",
    endpoint: "https://frink.apps.renci.org/prokn/sparql",
  },
  { 
    shortname: "ruralkg", 
    label: "Rural Resilience KG",    description: "Rural Resilience KG is a cross-domain knowledge graph to integrate health and justice for rural resilience.",
    endpoint: "https://frink.apps.renci.org/ruralkg/sparql",
  },
  { 
    shortname: "sawgraph", 
    label: "SAWGraph PFAS KG",    description: "The Safe Agricultural Products and Water Graph (SAWGraph) PFAS KG stores data on PFAS observations and releases, describing the samples, the geospatial features they were taken from, the sampled environmental media, the specific chemical substances and the measurement values observed.",
    endpoint: "https://frink.apps.renci.org/sawgraph/sparql",
  },
  { 
    shortname: "scales", 
    label: "SCALES",    description: "SCALES is an integrated justice platform to connect criminal justice data across data silos.",
    endpoint: "https://frink.apps.renci.org/scales/sparql",
  },
  { 
    shortname: "securechainkg", 
    label: "SecureChain KG",    description: "SecureChain is a knowledge graph for resilient, trustworthy, and secure software supply chains.",
    endpoint: "https://frink.apps.renci.org/securechainkg/sparql",
  },
  { 
    shortname: "semopenalex", 
    label: "SemOpenAlex",    description: "Comprehensive information on scientific publications and related entities.",
    endpoint: "https://frink.apps.renci.org/semopenalex/sparql",
  },
  { 
    shortname: "sockg", 
    label: "SOC-KG",    description: "The Soil Organic Carbon Knowledge Graph (SOCKG) enhances robust soil carbon modeling, which is crucial for voluntary carbon markets.",
    endpoint: "https://frink.apps.renci.org/sockg/sparql",
  },
  { 
    shortname: "spatialkg", 
    label: "SAWGraph Spatial KG",    description: "The SAWGraph Spatial KG is part of the Safe Agricultural Products and Water Graph (SAWGraph) project. It contains all the Level 13 grid cells from the S2 grid as well as administrative regions of levels 1 to 3 (states, counties, and county subdivisions) and the spatial relationships between them for the 48 contiguous states in the U.S.",
    endpoint: "https://frink.apps.renci.org/spatialkg/sparql",
  },
  { 
    shortname: "spoke-genelab", 
    label: "SPOKE GeneLab",    description: "The spoke-genelab KG complements the spokeokn (SPOKE Open Knowledge Network) KG and is designed to integrate omics data from NASA’s Open Science Data Repository (OSDR/GeneLab), which hosts results from spaceflight experiments.",
    endpoint: "https://frink.apps.renci.org/spoke-genelab/sparql",
  },
  { 
    shortname: "spoke-okn", 
    label: "SPOKE-OKN",    description: "The spoke-okn (SPOKE Open Knowledge Network) KG is a comprehensive biomedical and environmental health knowledge graph that integrates diverse data across genomics, environmental science, and public health.",
    endpoint: "https://frink.apps.renci.org/spoke-okn/sparql",
  },
  { 
    shortname: "sudokn", 
    label: "SUDOKN",    description: "Supply and Demand Open Knowledge Network is an interconnected network of publicly available manufacturing capability data focused on Small and Medium-Sized Manufacturers.",
    endpoint: "https://frink.apps.renci.org/sudokn/sparql",
  },
  { 
    shortname: "ubergraph", 
    label: "Ubergraph",    description: "Integrated suite of OBO ontologies with precomputed inferred relationships",
    endpoint: "https://frink.apps.renci.org/ubergraph/sparql",
  },
  { 
    shortname: "ufokn", 
    label: "UF-OKN",    description: "The Urban Flooding Open Knowledge Network (UF-OKN) is an informational infrastructure built using knowledge graphs aiming to extract structured content from the information scattered across open-source geospatial datasets and hydrologic models.",
    endpoint: "https://frink.apps.renci.org/ufokn/sparql",
  },
  { 
    shortname: "wikidata", 
    label: "Wikidata",    description: "Wikidata is a free and open knowledge base that can be read and edited by both humans and machines",
    endpoint: "https://frink.apps.renci.org/wikidata/sparql",
  },
  { 
    shortname: "wildlifekn", 
    label: "Wildlife-KN",    description: "This project seeks to create a comprehensive, integrative knowledge network for the management of wildlife in the context of climate change",
    endpoint: "https://frink.apps.renci.org/wildlifekn/sparql",
  }
];
