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
| `--mode` | `fast` (default) or `full`. `fast`: sampled queries + caps to reduce timeouts. `full`: no caps. |
| `--sample-triples` | Cap triples scanned when sampling (fast mode). Default: 200000. |
| `--max-object-props` | Max object properties to enrich with examples (fast mode). Default: 100. |
| `--max-restrictions` | Cap restriction rows per ontology query (fast mode). Default: 50000. |
| `--max-subproperty` | Cap subproperty rows (fast mode). Default: 50000. |

**Timeout avoidance (fast mode)**  
In `fast` mode, introspection uses sampled queries (subquery `LIMIT sample-triples`), caps on restriction and subproperty fetches, and ranks object properties by how many restriction rows they appear in—only the top `max-object-props` get example triples. Use `--mode full` to disable all caps.

```bash
# Default: fast mode (sampled + capped)
python scripts/build_graph_context.py build-one --graph nde --endpoint https://frink.apps.renci.org/nde/sparql --type knowledge_graph

# Full mode (no caps)
python scripts/build_graph_context.py build-one --graph ubergraph --endpoint https://frink.apps.renci.org/ubergraph/sparql --type ontology --mode full

# Custom caps (e.g. lighter sampling)
python scripts/build_graph_context.py build-one --graph nde --endpoint https://frink.apps.renci.org/nde/sparql --type knowledge_graph --sample-triples 100000 --max-object-props 50
```

#### build-frink

Discover graphs from the [FRINK OKN registry](https://frink.renci.org/registry/). The build fetches the registry index, parses shortnames from `kgs/{shortname}/` links, and constructs SPARQL endpoints as `https://frink.apps.renci.org/{shortname}/sparql` (per [kgs/nde/](https://frink.renci.org/registry/kgs/nde/) and similar per-KG pages). By default, builds all graphs **except** `ubergraph` and `wikidata` (those are excluded; use `build-one` or hand-maintained context for them). For each selected graph, run build-one and write `*_global.json`. `ubergraph` is built as `ontology`; others as `knowledge_graph`. If the registry is unavailable, falls back to `nde.yaml` and `ubergraph.yaml` for id/endpoint/type. If a graph returns an HTTP 5xx/429 or times out after retries, that graph is skipped and the build continues.

```bash
python scripts/build_graph_context.py build-frink
python scripts/build_graph_context.py build-frink --graphs nde
# Custom caps for each graph
python scripts/build_graph_context.py build-frink --sample-triples 100000 --max-object-props 50
```

**Options**

| Option | Description |
|--------|-------------|
| `--output-dir` | Directory for `*_global.json` (default: `web-v2/context/graphs`) |
| `--graphs` | Shortnames to build. Default: all from registry except `ubergraph` and `wikidata`. e.g. `--graphs nde` to build only nde. |
| `--registry-url` | FRINK registry URL (default: `https://frink.renci.org/registry/`) |
| `--timeout` | SPARQL/registry request timeout in seconds (default: 60). Graphs in `HEAVY_GRAPHS` (e.g. ubergraph, wikidata) use at least 300s for SPARQL. |
| `--mode`, `--sample-triples`, `--max-object-props`, `--max-restrictions`, `--max-subproperty` | Same as build-one; apply to each graph. |

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
| `--mode`, `--sample-triples`, `--max-object-props`, `--max-restrictions`, `--max-subproperty` | Same as build-one; apply to each OBO view. |

### Where files are written

- **build-one** (default): `web-v2/context/graphs/{graph}_global.json`
- **build-frink**: `web-v2/context/graphs/{shortname}_global.json` for each graph from the registry except `ubergraph` and `wikidata`; use `--graphs nde` to build only nde.
- **build-obo**: `web-v2/context/graphs/obo-{id}_global.json`

### Wikidata context (hand-maintained)

`wikidata_global.json` is **not** produced by `build_graph_context.py`. SPARQL introspection of the Wikidata graph (e.g. `get_top_classes` over `?s rdf:type ?class`) hits the FRINK wikidata endpoint with very heavy queries that frequently return 503. The file `web-v2/context/graphs/wikidata_global.json` is therefore **hand-maintained**: it curates endpoint, description, `good_for`, `uses_ontologies`, `notable_relationships`, `example_predicates`, `prefixes`, and a small set of `classes` and `properties` (e.g. wdt:P2175, P2176, P2293, P351, P5270, P685) from Wikidata’s documentation and from the project’s existing usage in `lib/ontology/templates.ts`, `lib/agents/query-planner.ts`, and `lib/ontology/wikidata-client.ts`. When updating, align property semantics with those (e.g. P2175 = drug→disease, P5270/wdtn:P5270 for MONDO mappings).

### Creating graph metadata YAML files

Graph metadata YAML files (`{graph}.yaml`) provide human-curated metadata that gets merged into the auto-generated `{graph}_global.json` files. They document use cases, notable relationships, example predicates, and query patterns that aren't easily derived from SPARQL introspection.

**Workflow for creating a new YAML file:**

1. **Build the JSON first** (if not already done):
   ```bash
   python scripts/build_graph_context.py build-frink --graphs gene-expression-atlas-okn
   ```
   This generates `web-v2/context/graphs/gene-expression-atlas-okn_global.json`.

2. **Copy the template**:
   ```bash
   cp web-v2/context/graphs/_template.yaml web-v2/context/graphs/gene-expression-atlas-okn.yaml
   ```

3. **Fill in the template**:
   - **`id`**: Graph shortname (must match filename)
   - **`endpoint`**: SPARQL endpoint URL (for FRINK: `https://frink.apps.renci.org/{shortname}/sparql`)
   - **`description`**: Brief description (optional; auto-generated if omitted)
   - **`good_for`**: Use cases (e.g. `["dataset_search", "entity_lookup"]`)
   - **`notable_relationships`**: Key relationship patterns (e.g. "Datasets to diseases via schema:healthCondition")
   - **`example_predicates`**: Important predicates with descriptions (check `*_global.json` for top properties)
   - **`queryable_by`**: Entity types and properties for querying (optional)
   - **`provides_ontologies`**: Ontologies this graph provides (optional)

4. **Use the JSON to inform your YAML**:
   - Open `{graph}_global.json` to see:
     - Top classes → suggest `good_for` (e.g. if `schema:Dataset` is top class, include `"dataset_search"`)
     - Top properties → candidates for `example_predicates`
     - Properties with examples → candidates for `queryable_by`
     - `uses_ontologies` → can inform `provides_ontologies` if this graph is the source

5. **Rebuild the JSON** to merge your YAML metadata:
   ```bash
   python scripts/build_graph_context.py build-one \
     --graph gene-expression-atlas-okn \
     --endpoint https://frink.apps.renci.org/gene-expression-atlas-okn/sparql \
     --type knowledge_graph
   ```

**Examples:**
- `nde.yaml` - Knowledge graph with dataset search use case
- `wikidata.yaml` - Entity lookup and relationships
- `ubergraph.yaml` - Ontology reasoning with many provided ontologies

**Template location:** `web-v2/context/graphs/_template.yaml`

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
