# Scripts

## build_graph_context.py

Build graph context JSON files (`*_global.json`) for FRINK knowledge graphs and ontologies. Output is consumed by `web-v2/lib/graph-context` (LocalFileProvider, adapter). Requires: `requests`, `PyYAML` (for merging `description` and other metadata from `{graph}.yaml`).

### Subcommands

#### build-one

Introspect one graph and write a context file. **Graph-derived metadata** (at the top of the JSON): `description` and `uses_ontologies` are inferred from the graph (IRI patterns in classes, properties, and examples; OBO, UniProt taxonomy, etc.). When a co-located `{graph}.yaml` exists, it can override `description` and supply `good_for`, `notable_relationships`, `example_predicates`, `queryable_by`; `uses_ontologies` is never taken from YAML. **Property examples** are capped at 5; when all object values follow the same IRI/literal pattern, only 3 are kept.

```bash
# Knowledge graph (e.g. NDE): primary class schema:Dataset, dataset_properties, relationship examples
python scripts/build_graph_context.py build-one \
  --graph nde \
  --endpoint https://frink.apps.renci.org/nde/sparql \
  --type knowledge_graph

# Ontology (e.g. Ubergraph): top classes/predicates, object_properties from OWL axioms, rdfs:label/synonym examples
python scripts/build_graph_context.py build-one \
  --graph ubergraph \
  --endpoint https://frink.apps.renci.org/ubergraph/sparql \
  --type ontology
```

**Options**

| Option | Description |
|--------|-------------|
| `--graph` | Graph shortname (e.g. `nde`, `ubergraph`) |
| `--endpoint` | SPARQL endpoint URL |
| `--type` | `knowledge_graph` or `ontology` |
| `--output` | Output path (default: `web-v2/context/graphs/{graph}_global.json`) |
| `--primary-class` | For `knowledge_graph`: primary class IRI (default: `http://schema.org/Dataset`) |
| `--iri-prefix` | For `ontology`: restrict to entities whose IRI starts with this (e.g. `http://purl.obolibrary.org/obo/MONDO_`) |
| `--timeout` | SPARQL request timeout in seconds (default: 60) |

#### build-frink

Discover graphs from the [FRINK OKN registry](https://frink.renci.org/registry/). The build fetches the registry index, parses shortnames from `kgs/{shortname}/` links, and constructs SPARQL endpoints as `https://frink.apps.renci.org/{shortname}/sparql` (per [kgs/nde/](https://frink.renci.org/registry/kgs/nde/) and similar per-KG pages). By default, builds all graphs **except** `ubergraph` and `wikidata` (those are excluded; use `build-one` or hand-maintained context for them). For each selected graph, run build-one and write `*_global.json`. `ubergraph` is built as `ontology`; others as `knowledge_graph`. If the registry is unavailable, falls back to `nde.yaml` and `ubergraph.yaml` for id/endpoint/type. If a graph returns an HTTP 5xx/429 or times out after retries, that graph is skipped and the build continues.

```bash
python scripts/build_graph_context.py build-frink
python scripts/build_graph_context.py build-frink --graphs nde
```

**Options**

| Option | Description |
|--------|-------------|
| `--output-dir` | Directory for `*_global.json` (default: `web-v2/context/graphs`) |
| `--graphs` | Shortnames to build. Default: all from registry except `ubergraph` and `wikidata`. e.g. `--graphs nde` to build only nde. |
| `--registry-url` | FRINK registry URL (default: `https://frink.renci.org/registry/`) |
| `--timeout` | SPARQL/registry request timeout in seconds (default: 60). Graphs in `HEAVY_GRAPHS` (e.g. ubergraph, wikidata) use at least 300s for SPARQL. |

#### build-obo

Per-OBO ontology views over Ubergraph: for each OBO id (e.g. MONDO, GO, HP), run ontology-style introspection restricted to that ontology’s IRI prefix and write `obo-{id}_global.json`.

```bash
python scripts/build_graph_context.py build-obo --obo MONDO GO HP
```

**Options**

| Option | Description |
|--------|-------------|
| `--obo` | OBO ids (default: `MONDO GO HP`) |
| `--endpoint` | Ubergraph SPARQL endpoint (default: `https://frink.apps.renci.org/ubergraph/sparql`) |
| `--output-dir` | Directory for `obo-{id}_global.json` (default: `web-v2/context/graphs`) |
| `--timeout` | SPARQL timeout (default: 60) |

### Where files are written

- **build-one** (default): `web-v2/context/graphs/{graph}_global.json`
- **build-frink**: `web-v2/context/graphs/{shortname}_global.json` for each graph from the registry except `ubergraph` and `wikidata`; use `--graphs nde` to build only nde.
- **build-obo**: `web-v2/context/graphs/obo-{id}_global.json`

### Wikidata context (hand-maintained)

`wikidata_global.json` is **not** produced by `build_graph_context.py`. SPARQL introspection of the Wikidata graph (e.g. `get_top_classes` over `?s rdf:type ?class`) hits the FRINK wikidata endpoint with very heavy queries that frequently return 503. The file `web-v2/context/graphs/wikidata_global.json` is therefore **hand-maintained**: it curates endpoint, description, `good_for`, `uses_ontologies`, `notable_relationships`, `example_predicates`, `prefixes`, and a small set of `classes` and `properties` (e.g. wdt:P2175, P2176, P2293, P351, P5270, P685) from Wikidata’s documentation and from the project’s existing usage in `lib/ontology/templates.ts`, `lib/agents/query-planner.ts`, and `lib/ontology/wikidata-client.ts`. When updating, align property semantics with those (e.g. P2175 = drug→disease, P5270/wdtn:P5270 for MONDO mappings).

---

## Environment variables (web-v2 / graph-context)

| Variable | Description |
|----------|-------------|
| `GRAPH_CONTEXT_DIR` | Directory for `*_global.json`. LocalFileProvider uses this when set; otherwise `{process.cwd()}/context/graphs` (e.g. `web-v2/context/graphs` when running from `web-v2`). |
| `DISABLE_GITHUB_CONTEXT` | Set to `1` or `true` to omit `GitHubContextProvider` from the loader so WOBD uses only local context files. |
| `GITHUB_CONTEXT_URL` | Base URL for GitHub-hosted `*_global.json` (used by `GitHubContextProvider` when not disabled). When unset, the GitHub provider does not fetch. |

---

## build_nde_context.py

Legacy script for NDE only. Prefer `build_graph_context.py build-one --graph nde --type knowledge_graph` (or `build-frink` for nde + ubergraph).
