# OKN-WOBD

Extract data from the [NIAID Data Ecosystem Discovery Portal](https://data.niaid.nih.gov/) and convert for loading into [ProtoOKN](https://www.proto-okn.net/).

## Python Environment Setup

Use `pyenv` to install the Python version needed, then create an isolated `venv` in the repository:

```bash
pyenv install 3.12.6
pyenv local 3.12.6
python -m venv .venv
source .venv/bin/activate     # on Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -e .
```

## Fetching NDE Data

Run the Click CLI (installed as the `okn-wobd` console script) to download dataset records for one or more resources. By default, results are written to `data/raw` as JSON Lines (`*.jsonl`) with matching checkpoint files (`*_state.json`) to support restarts.

```bash
okn-wobd fetch --resource ImmPort
# or, equivalently:
python -m okn_wobd.cli fetch --resource ImmPort
```

### Options

- `--resource`: Repeatable; defaults to `ImmPort` when omitted. Examples: `ImmPort`, `"VDJ Server"`, `Vivli`, `RADx`, `PDB`, `"Project TYCHO"`.
- `--output-dir`: Directory for saved data and checkpoints (default: `data/raw`).
- `--page-size`: Batch size for API pagination (default: 100, maximum: 1000).
- `--facet-size`: Passed through to the API facet parameter (default: 10).
- `--restart`: Ignore previous checkpoints and start from the first page.
- `--verbose`: Emit detailed logging.
- `--max-window`: Maximum result window before automatic segmentation (default: 10,000).
- `--segment-field`, `--segment-charset`, `--segment-max-length`: Controls for prefix-based segmentation when a catalog exceeds the result window.

### Restarting After Failures

The CLI records progress for each resource in `<output-dir>/<resource>_state.json`. Rerun the command without `--restart` to resume where it left off. Supply `--restart` to discard prior results and fetch everything again from the beginning.

### Example: Fetch Multiple Resources

```bash
python -m okn_wobd.cli fetch \
  --resource ImmPort \
  --resource "VDJ Server" \
  --resource Vivli
```

This will create separate JSONL and checkpoint files for each resource under `data/raw/`.

### Handling Resources with >10k Records

Elasticsearch-backed endpoints limit `from + size <= 10,000`. When a catalog (for example, `Protein Data Bank`) exceeds that window, the CLI automatically partitions requests by prefix on the `identifier` field. You can tune the behavior:

```bash
okn-wobd fetch \
  --resource "Protein Data Bank" \
  --max-window 10000 \
  --segment-field identifier \
  --segment-charset 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ \
  --segment-max-length 4
```

The state file tracks both the current segment and offset so interrupted runs can resume without re-downloading data.

## Summarizing Downloaded JSONL Files

After fetching data, generate a quick overview of record counts and coverage of disease/species/infectious-agent metadata:

```bash
python scripts/summarize_jsonl.py
```

The script scans `data/raw/*.jsonl`, writes the results to `reports/jsonl_summary.md`, and prints the table to stdout.

## Listing Top-Level Fields in JSONL Files

```bash
python scripts/list_jsonl_fields.py
```

This writes a field inventory to `reports/jsonl_fields.md`.