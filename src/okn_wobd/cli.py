from __future__ import annotations

import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, Iterable, List, Optional

import click
import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ChunkedEncodingError, ConnectionError, Timeout
from urllib3.util.retry import Retry

from okn_wobd.rdf_converter import convert_jsonl_to_rdf
from okn_wobd.excluded_resources import EXCLUDED_RESOURCES

BASE_URL = "https://api.data.niaid.nih.gov/v1/query"
METADATA_URL = "https://api.data.niaid.nih.gov/v1/metadata?format=json"
DEFAULT_PAGE_SIZE = 100
DEFAULT_FACET_SIZE = 10
DEFAULT_SEGMENT_FIELD = "identifier"
DEFAULT_SEGMENT_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DEFAULT_MAX_PREFIX_LENGTH = 6
MAX_RESULT_WINDOW = 10_000


@dataclass
class FetchState:
    resource: str
    mode: str = "linear"
    next_offset: int = 0
    total: Optional[int] = None
    segments: List[dict] = field(default_factory=list)
    segment_index: int = 0
    segment_offset: int = 0

    @classmethod
    def load(cls, path: Path) -> "FetchState":
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        return cls(
            resource=payload["resource"],
            mode=payload.get("mode", "linear"),
            next_offset=payload.get("next_offset", 0),
            total=payload.get("total"),
            segments=payload.get("segments", []),
            segment_index=payload.get("segment_index", 0),
            segment_offset=payload.get("segment_offset", 0),
        )

    def dump(self, path: Path) -> None:
        payload = {
            "resource": self.resource,
            "mode": self.mode,
            "next_offset": self.next_offset,
            "total": self.total,
            "segments": self.segments,
            "segment_index": self.segment_index,
            "segment_offset": self.segment_offset,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)


def configure_session(timeout: int = 30) -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=2.0,  # Increased from 1.0 for better rate limit handling
        status_forcelist=(429, 500, 502, 503, 504),  # Added 429 for rate limiting
        allowed_methods=("GET",),
        respect_retry_after_header=True,  # Respect Retry-After header from API
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": "OKN-WOBD/0.1 (+https://github.com/SuLab/OKN-WOBD)"})
    session.request = _wrap_with_timeout(session.request, timeout=timeout)
    return session


def _wrap_with_timeout(request_method, timeout: int):
    def request_with_timeout(method, url, **kwargs):
        kwargs.setdefault("timeout", timeout)
        return request_method(method, url, **kwargs)

    return request_with_timeout


def slugify(value: str) -> str:
    clean = "".join(ch if ch.isalnum() else "_" for ch in value)
    while "__" in clean:
        clean = clean.replace("__", "_")
    return clean.strip("_").lower() or "resource"


def build_extra_filter(resource: str) -> str:
    resource_filter = f'(includedInDataCatalog.name:("{resource}"))'
    dataset_filter = '(@type:("Dataset"))'
    return f"{resource_filter} AND {dataset_filter}"


def get_all_resources_from_api(
    session: requests.Session,
) -> List[str]:
    """Query the NDE API to get all available Dataset Repository resources.
    
    This function uses the metadata endpoint to get all registered sources,
    then filters for those that have datasets (Dataset Repositories).
    Resources listed in EXCLUDED_RESOURCES are automatically excluded.
    An excluded resources log file is saved to reports/excluded_resources_log.json.
    
    Args:
        session: Configured requests session
    
    Returns:
        List of unique resource names that have datasets
    """
    excluded_set = set(EXCLUDED_RESOURCES)
    resources = set()
    excluded_resources = []
    sources_without_datasets = []
    
    click.echo("Querying NDE metadata API to discover all Dataset Repositories...")
    
    try:
        # Get metadata for all sources
        response = session.get(METADATA_URL, timeout=30)
        response.raise_for_status()
        metadata = response.json()
        sources = metadata.get("src", {})
        
        click.echo(f"  Found {len(sources)} registered sources in metadata")
        
        # Filter for sources that have datasets (Dataset Repositories)
        for key, source in sources.items():
            if "sourceInfo" not in source:
                continue
            
            info = source.get("sourceInfo", {})
            source_name = info.get("name") or info.get("identifier") or key
            
            # Check if excluded
            if source_name in excluded_set:
                excluded_resources.append({
                    "name": source_name,
                    "reason": "explicitly excluded",
                    "has_datasets": False,
                })
                continue
            
            # Check if this source has datasets
            stats = source.get("stats", {})
            has_datasets = False
            dataset_count = 0
            
            if isinstance(stats, dict):
                # Check if any stat value indicates datasets
                for stat_value in stats.values():
                    if isinstance(stat_value, (int, float)) and stat_value > 0:
                        has_datasets = True
                        dataset_count = max(dataset_count, stat_value)
                        break
            
            if has_datasets:
                resources.add(source_name)
            else:
                sources_without_datasets.append({
                    "name": source_name,
                    "reason": "no datasets",
                    "dataset_count": 0,
                })
        
        click.echo(f"  Found {len(resources)} Dataset Repositories (sources with datasets)")
        click.echo(f"  Excluded {len(excluded_resources)} resources (explicitly excluded)")
        click.echo(f"  Skipped {len(sources_without_datasets)} sources (no datasets)")
        
        # Save excluded resources log file to default reports directory
        log_dir = Path("reports")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "excluded_resources_log.json"
        
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "excluded_resources": excluded_resources,
            "sources_without_datasets": sources_without_datasets,
            "total_sources": len(sources),
            "dataset_repositories_found": len(resources),
        }
        
        with log_file.open("w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2)
        
        click.echo(f"  Excluded resources log saved to {log_file}")
        
        if not resources:
            click.echo(
                "Warning: No Dataset Repositories found from metadata.",
                err=True,
            )
            return []
        
        return sorted(resources)
    
    except Exception as e:
        click.echo(
            f"Error: Could not fetch resources from metadata API: {e}",
            err=True,
        )
        raise click.Abort("Failed to discover resources from NDE API. Cannot proceed with --all flag.")


def build_query(prefix: str, segment_field: str) -> str:
    if prefix:
        return f"{segment_field}:{prefix}*"
    return "*"


def request_payload(
    session: requests.Session,
    extra_filter: str,
    facet_size: int,
    size: int,
    offset: int,
    query: str,
    max_retries: int = 5,
) -> dict:
    """Request payload from API with retry logic for network errors."""
    params = {
        "q": query,
        "extra_filter": extra_filter,
        "facet_size": facet_size,
        "size": size,
    }
    if offset:
        params["from"] = offset
    
    last_error = None
    for attempt in range(max_retries):
        try:
            response = session.get(BASE_URL, params=params, stream=False)
            response.raise_for_status()
            # Access content to trigger any ChunkedEncodingError before parsing JSON
            # This ensures we catch the error in our retry loop
            try:
                return response.json()
            except (ChunkedEncodingError, ValueError) as e:
                # ValueError can occur if JSON parsing fails due to incomplete response
                # ChunkedEncodingError occurs when response is cut off
                raise ChunkedEncodingError(f"Failed to read complete response: {e}") from e
        except (ChunkedEncodingError, ConnectionError, Timeout) as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                click.echo(
                    f"Network error (attempt {attempt + 1}/{max_retries}): {e}. "
                    f"Retrying in {wait_time} seconds...",
                    err=True,
                )
                time.sleep(wait_time)
            else:
                click.echo(
                    f"Failed after {max_retries} attempts: {e}",
                    err=True,
                )
                raise
        except requests.HTTPError as e:
            # Don't retry HTTP errors (4xx, 5xx) - let them propagate
            raise
    
    # Should never reach here, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected error in request_payload")


def query_total(
    session: requests.Session,
    extra_filter: str,
    facet_size: int,
    query: str,
) -> int:
    payload = request_payload(
        session=session,
        extra_filter=extra_filter,
        facet_size=facet_size,
        size=0,
        offset=0,
        query=query,
    )
    total = payload.get("total")
    return int(total) if total is not None else 0


def compute_segments(
    session: requests.Session,
    extra_filter: str,
    facet_size: int,
    segment_field: str,
    charset: str,
    max_window: int,
    max_prefix_length: int,
    warnings: Optional[List[dict]] = None,
) -> List[dict]:
    total = query_total(
        session=session,
        extra_filter=extra_filter,
        facet_size=facet_size,
        query=build_query("", segment_field),
    )
    if total <= max_window:
        return [{"prefix": "", "total": total}]

    segments: List[dict] = []
    pending: Deque[tuple[str, int, int]] = deque()
    seen: set[str] = set()

    pending.append(("", total, 0))
    seen.add("")

    while pending:
        prefix, prefix_total, depth = pending.popleft()

        if prefix_total == 0:
            continue

        # API limit: from + size <= max_window, so we need segments with total < max_window
        # Use max_window - 1 as the safe limit to ensure we can always fetch all records
        safe_limit = max_window - 1
        
        if prefix_total <= safe_limit:
            segments.append({"prefix": prefix, "total": prefix_total})
            continue
        
        # If we've reached max depth and still exceed limit, we have a problem
        # We'll still create the segment but it will be capped during fetch
        if depth >= max_prefix_length:
            if prefix_total > safe_limit:
                warning_msg = (
                    f"prefix '{prefix}' reached max depth ({max_prefix_length}) with {prefix_total} records "
                    f"(exceeds safe limit of {safe_limit}). Some records may not be fetchable. "
                    f"Consider increasing --segment-max-length to allow further sub-segmentation."
                )
                click.echo(f"Warning: {warning_msg}", err=True)
                if warnings is not None:
                    warnings.append({
                        "type": "max_depth_exceeded",
                        "prefix": prefix,
                        "depth": depth,
                        "record_count": prefix_total,
                        "safe_limit": safe_limit,
                        "max_prefix_length": max_prefix_length,
                        "message": warning_msg,
                    })
            # Cap the segment total to safe limit
            segments.append({"prefix": prefix, "total": safe_limit})
            continue

        for char in charset:
            child_prefix = prefix + char
            if child_prefix in seen:
                continue

            child_total = query_total(
                session=session,
                extra_filter=extra_filter,
                facet_size=facet_size,
                query=build_query(child_prefix, segment_field),
            )
            seen.add(child_prefix)
            if child_total:
                pending.append((child_prefix, child_total, depth + 1))

    segments.sort(key=lambda item: item["prefix"])
    return segments or [{"prefix": "", "total": total}]


def fetch_resource(
    session: requests.Session,
    resource: str,
    output_dir: Path,
    page_size: int,
    facet_size: int,
    restart: bool,
    max_window: int,
    segment_field: str,
    segment_charset: str,
    segment_max_length: int,
) -> Path:
    slug = slugify(resource)
    data_path = output_dir / f"{slug}.jsonl"
    state_path = output_dir / f"{slug}_state.json"

    if restart:
        for path in (data_path, state_path):
            if path.exists():
                path.unlink()

    if state_path.exists() and data_path.exists():
        state = FetchState.load(state_path)
        click.echo(f"Resuming {resource!r} (mode: {state.mode}).")
    else:
        state = FetchState(resource=resource)
        click.echo(f"Starting {resource!r} from scratch.")

    output_dir.mkdir(parents=True, exist_ok=True)

    extra_filter = build_extra_filter(resource)

    # Collect all warnings for this resource
    resource_warnings = []

    if state.mode == "linear" and (state.total is None or state.total <= max_window):
        total = query_total(
            session=session,
            extra_filter=extra_filter,
            facet_size=facet_size,
            query=build_query("", segment_field),
        )
        state.total = total
        state.dump(state_path)
        if total > max_window:
            click.echo(
                f"{resource!r} has {total} records; switching to segmented fetch to respect "
                f"result window limit ({max_window})."
            )
            state.mode = "segmented"
            # Collect warnings during segmentation
            state.segments = compute_segments(
                session=session,
                extra_filter=extra_filter,
                facet_size=facet_size,
                segment_field=segment_field,
                charset=segment_charset,
                max_window=max_window,
                max_prefix_length=segment_max_length,
                warnings=resource_warnings,
            )
            state.segment_index = 0
            state.segment_offset = 0
            state.dump(state_path)
    elif state.mode == "segmented" and not state.segments:
        # Collect warnings during segmentation
        state.segments = compute_segments(
            session=session,
            extra_filter=extra_filter,
            facet_size=facet_size,
            segment_field=segment_field,
            charset=segment_charset,
            max_window=max_window,
            max_prefix_length=segment_max_length,
            warnings=resource_warnings,
        )
        state.dump(state_path)
    
    with data_path.open("a", encoding="utf-8") as data_file:
        if state.mode == "segmented":
            fetch_segmented(
                session=session,
                data_file=data_file,
                state_path=state_path,
                state=state,
                page_size=page_size,
                facet_size=facet_size,
                extra_filter=extra_filter,
                segment_field=segment_field,
                max_window=max_window,
                warnings=resource_warnings,
            )
        else:
            fetch_linear(
                session=session,
                data_file=data_file,
                state_path=state_path,
                state=state,
                page_size=page_size,
                facet_size=facet_size,
                extra_filter=extra_filter,
            )
    
    # Save warnings to log file if any were generated
    if resource_warnings:
        log_dir = Path("reports")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "segmentation_warnings_log.json"
        
        # Load existing warnings if file exists
        existing_warnings = []
        if log_file.exists():
            try:
                with log_file.open("r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    existing_warnings = existing_data.get("warnings", [])
            except (json.JSONDecodeError, KeyError):
                existing_warnings = []
        
        # Add resource name and timestamp to warnings that don't have them
        for warning in resource_warnings:
            if "resource" not in warning:
                warning["resource"] = resource
            if "timestamp" not in warning:
                warning["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        # Combine and save
        all_warnings = existing_warnings + resource_warnings
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "warnings": all_warnings,
        }
        
        with log_file.open("w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2)
        
        click.echo(f"  {len(resource_warnings)} segmentation warning(s) logged to {log_file}")

    return data_path


def fetch_linear(
    session: requests.Session,
    data_file,
    state_path: Path,
    state: FetchState,
    page_size: int,
    facet_size: int,
    extra_filter: str,
) -> None:
    offset = state.next_offset
    total = state.total

    click.echo(
        f"Fetching {state.resource!r} in linear mode starting at offset {offset} "
        f"(total={total if total is not None else 'unknown'})."
    )

    while True:
        payload = request_payload(
            session=session,
            extra_filter=extra_filter,
            facet_size=facet_size,
            size=page_size,
            offset=offset,
            query="*",
        )
        hits = payload.get("hits", [])
        total = payload.get("total", total)

        if not hits:
            click.echo(
                f"No more records for {state.resource!r}. Fetched {offset} in total."
            )
            break

        for item in hits:
            data_file.write(json.dumps(item))
            data_file.write("\n")

        offset += len(hits)
        state.next_offset = offset
        state.total = total
        state.dump(state_path)

        click.echo(
            f"Fetched {offset}/{total if total is not None else '?'} "
            f"records for {state.resource!r}."
        )

        if total is not None and offset >= total:
            click.echo(
                f"Completed fetching all {total} records for {state.resource!r}."
            )
            break


def fetch_segmented(
    session: requests.Session,
    data_file,
    state_path: Path,
    state: FetchState,
    page_size: int,
    facet_size: int,
    extra_filter: str,
    segment_field: str,
    max_window: int,
    warnings: Optional[List[dict]] = None,
) -> None:
    segments = state.segments or [{"prefix": "", "total": 0}]
    grand_total = sum(int(seg.get("total", 0)) for seg in segments)

    click.echo(
        f"Fetching {state.resource!r} across {len(segments)} segment(s). "
        f"Total records (approx): {grand_total}."
    )

    for idx in range(state.segment_index, len(segments)):
        segment = segments[idx]
        prefix = segment.get("prefix", "")
        segment_total = int(segment.get("total", 0))
        offset = state.segment_offset if idx == state.segment_index else 0

        if segment_total == 0:
            state.segment_index = idx + 1
            state.segment_offset = 0
            state.dump(state_path)
            continue

        click.echo(
            f"Segment {idx + 1}/{len(segments)} prefix='{prefix}' "
            f"({segment_total} records)."
        )

        # Cap segment_total to ensure we never exceed API limit
        # API limit: from + size <= max_window, so max offset is max_window - 1
        max_allowed_offset = max_window - 1
        effective_segment_total = min(segment_total, max_allowed_offset + 1)
        
        if segment_total > max_allowed_offset + 1:
            warning_msg = (
                f"Segment '{prefix}' has {segment_total} records but API limit allows max offset {max_allowed_offset}. "
                f"Will only fetch first {effective_segment_total} records. Segment needs further sub-segmentation."
            )
            click.echo(f"Warning: {warning_msg}", err=True)
            if warnings is not None:
                warnings.append({
                    "type": "segment_exceeds_limit",
                    "resource": state.resource,
                    "prefix": prefix,
                    "segment_total": segment_total,
                    "max_allowed_offset": max_allowed_offset,
                    "effective_segment_total": effective_segment_total,
                    "records_skipped": segment_total - effective_segment_total,
                    "message": warning_msg,
                })
        
        while offset < effective_segment_total:
            # Calculate size ensuring offset + size <= max_window
            remaining_in_segment = effective_segment_total - offset
            max_size_for_offset = max_window - offset  # offset + size must be <= max_window
            size = min(page_size, remaining_in_segment, max_size_for_offset)
            
            if size <= 0:
                # Can't fetch more without exceeding limit
                break
            
            try:
                payload = request_payload(
                    session=session,
                    extra_filter=extra_filter,
                    facet_size=facet_size,
                    size=size,
                    offset=offset,
                    query=build_query(prefix, segment_field),
                )
            except requests.HTTPError as e:
                if "search_phase_execution_exception" in str(e) or "400" in str(e):
                    error_msg = (
                        f"API limit reached at offset {offset} for segment '{prefix}'. "
                        f"Segment needs further sub-segmentation. Consider increasing --segment-max-length."
                    )
                    click.echo(f"Error: {error_msg}", err=True)
                    if warnings is not None:
                        warnings.append({
                            "type": "api_limit_hit",
                            "resource": state.resource,
                            "prefix": prefix,
                            "offset": offset,
                            "max_window": max_window,
                            "message": error_msg,
                        })
                    break
                raise
            hits = payload.get("hits", [])

            if not hits:
                click.echo(
                    f"No more records in segment '{prefix}' after offset {offset}."
                )
                break

            for item in hits:
                data_file.write(json.dumps(item))
                data_file.write("\n")

            offset += len(hits)
            state.segment_index = idx
            state.segment_offset = offset
            state.dump(state_path)

            click.echo(
                f"Segment '{prefix}' progress: {offset}/{segment_total} "
                f"records for {state.resource!r}."
            )

            if offset >= segment_total:
                break

        state.segment_index = idx + 1
        state.segment_offset = 0
        state.dump(state_path)

    click.echo(f"Completed segmented fetch for {state.resource!r}.")


@click.group()
@click.option("--verbose", is_flag=True, help="Enable verbose logging.")
def cli(verbose: bool) -> None:
    """CLI utilities for working with the NIAID dataset API."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)


@cli.command("fetch")
@click.option(
    "--resource",
    "resources",
    multiple=True,
    type=str,
    help=(
        "Catalog resource to fetch (repeat for multiple). "
        "Defaults to ImmPort if omitted."
    ),
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("data/raw"),
    show_default=True,
    help="Directory to write JSONL output and checkpoint files.",
)
@click.option(
    "--page-size",
    type=click.IntRange(1, 1000),
    default=DEFAULT_PAGE_SIZE,
    show_default=True,
    help="Number of records to request per API call.",
)
@click.option(
    "--facet-size",
    type=click.IntRange(1, 100),
    default=DEFAULT_FACET_SIZE,
    show_default=True,
    help="Facet size parameter to include with each request.",
)
@click.option(
    "--restart",
    is_flag=True,
    help="Discard prior checkpoints and start fresh for each resource.",
)
@click.option(
    "--max-window",
    type=click.IntRange(1000, 1_000_000),
    default=MAX_RESULT_WINDOW,
    show_default=True,
    help="Maximum allowed result window (API limit).",
)
@click.option(
    "--segment-field",
    default=DEFAULT_SEGMENT_FIELD,
    show_default=True,
    help="Field used to partition large datasets (prefix search).",
)
@click.option(
    "--segment-charset",
    default=DEFAULT_SEGMENT_CHARSET,
    show_default=True,
    help="Characters to use when expanding prefixes for segmentation.",
)
@click.option(
    "--segment-max-length",
    type=click.IntRange(1, 12),
    default=DEFAULT_MAX_PREFIX_LENGTH,
    show_default=True,
    help="Maximum prefix length when segmenting large datasets.",
)
@click.option(
    "--all",
    "fetch_all",
    is_flag=True,
    help="Fetch all available resources from NDE API (excluding configured exclusions).",
)
def fetch_command(
    resources: Iterable[str],
    output_dir: Path,
    page_size: int,
    facet_size: int,
    restart: bool,
    max_window: int,
    segment_field: str,
    segment_charset: str,
    segment_max_length: int,
    fetch_all: bool,
) -> None:
    """Fetch dataset records from the NIAID API for one or more resources."""
    session = configure_session()
    
    if fetch_all:
        # Get all resources from API, excluding configured exclusions
        chosen_resources = get_all_resources_from_api(
            session=session,
        )
        if not chosen_resources:
            click.echo("No resources found after applying exclusions.", err=True)
            return
        click.echo(f"Found {len(chosen_resources)} resources to fetch: {', '.join(chosen_resources)}")
    else:
        chosen_resources = tuple(resources) or ("ImmPort",)

    if not segment_field.strip():
        raise click.BadParameter("segment-field must not be empty.", param_name="segment_field")
    if not segment_charset:
        raise click.BadParameter("segment-charset must not be empty.", param_name="segment_charset")
    segment_charset = "".join(dict.fromkeys(segment_charset))

    # Track fetch results
    completed_resources = []
    failed_resources = []
    incomplete_resources = []

    for resource in chosen_resources:
        try:
            data_path = fetch_resource(
                session=session,
                resource=resource,
                output_dir=output_dir,
                page_size=page_size,
                facet_size=facet_size,
                restart=restart,
                max_window=max_window,
                segment_field=segment_field,
                segment_charset=segment_charset,
                segment_max_length=segment_max_length,
            )
            click.echo(f"Data for {resource!r} saved to {data_path}.")
        except (requests.HTTPError, ChunkedEncodingError, ConnectionError, Timeout) as exc:
            click.echo(
                f"Failed to fetch {resource!r} after retries: {exc}. "
                f"Skipping and continuing with next resource.",
                err=True,
            )
            # Don't continue yet - check state file below
        
        # Check if fetch is complete by comparing state (for both successful and failed fetches)
        slug = slugify(resource)
        state_path = output_dir / f"{slug}_state.json"
        data_path = output_dir / f"{slug}.jsonl"
        
        if state_path.exists():
            try:
                state = FetchState.load(state_path)
                
                # Calculate fetched count based on mode
                if state.mode == "segmented":
                    # For segmented mode, calculate from segments
                    fetched = 0
                    # Sum completed segments (segments 0 to segment_index-1)
                    for i in range(state.segment_index):
                        if i < len(state.segments):
                            fetched += state.segments[i].get("total", 0)
                    # Add current segment progress
                    if state.segment_index < len(state.segments):
                        fetched += state.segment_offset
                else:
                    # For linear mode, use next_offset
                    fetched = state.next_offset
                
                if state.total is not None and fetched < state.total:
                    # Incomplete fetch
                    incomplete_resources.append({
                        "resource": resource,
                        "fetched": fetched,
                        "total": state.total,
                        "remaining": state.total - fetched,
                        "data_file": str(data_path),
                        "state_file": str(state_path),
                    })
                else:
                    completed_resources.append(resource)
            except Exception:
                # If we can't read state, treat as failed
                if resource not in [r["resource"] for r in incomplete_resources]:
                    failed_resources.append({
                        "resource": resource,
                        "error": "Could not read state file",
                        "error_type": "StateReadError",
                    })
        else:
            # No state file means it failed completely (or was never started)
            if resource not in [r["resource"] for r in incomplete_resources]:
                failed_resources.append({
                    "resource": resource,
                    "error": "No state file found - fetch did not start or was cleared",
                    "error_type": "NoStateFile",
                })
    
    # Generate summary report
    if completed_resources or failed_resources or incomplete_resources:
        log_dir = Path("reports")
        log_dir.mkdir(parents=True, exist_ok=True)
        summary_file = log_dir / "fetch_summary.json"
        
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_resources": len(chosen_resources),
            "completed": len(completed_resources),
            "incomplete": len(incomplete_resources),
            "failed": len(failed_resources),
            "completed_resources": completed_resources,
            "incomplete_resources": incomplete_resources,
            "failed_resources": failed_resources,
        }
        
        with summary_file.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        
        click.echo("\n" + "=" * 60)
        click.echo("FETCH SUMMARY")
        click.echo("=" * 60)
        click.echo(f"Total resources: {len(chosen_resources)}")
        click.echo(f"✓ Completed: {len(completed_resources)}")
        if incomplete_resources:
            click.echo(f"⚠ Incomplete: {len(incomplete_resources)} (see details below)")
        if failed_resources:
            click.echo(f"✗ Failed: {len(failed_resources)} (see details below)")
        click.echo(f"\nDetailed summary saved to: {summary_file}")
        
        if incomplete_resources:
            click.echo("\nINCOMPLETE RESOURCES (run again to resume):")
            for item in incomplete_resources:
                click.echo(
                    f"  - {item['resource']}: {item['fetched']}/{item['total']} records "
                    f"({item['remaining']} remaining)"
                )
        
        if failed_resources:
            click.echo("\nFAILED RESOURCES (check errors and retry manually):")
            for item in failed_resources:
                click.echo(f"  - {item['resource']}: {item['error_type']}")
        click.echo("=" * 60)


@cli.command("convert")
@click.option(
    "--input-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=Path("data/raw"),
    show_default=True,
    help="Directory containing JSONL input files.",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("data/rdf"),
    show_default=True,
    help="Directory to write N-Triples output files.",
)
@click.option(
    "--resource",
    "resources",
    multiple=True,
    type=str,
    help=(
        "Resource to convert (repeat for multiple). "
        "If omitted, converts all JSONL files found in input directory."
    ),
)
def convert_command(
    input_dir: Path,
    output_dir: Path,
    resources: Iterable[str],
) -> None:
    """Convert JSONL dataset files to RDF N-Triples format."""
    chosen_resources = tuple(resources) if resources else None
    
    # Find all JSONL files in input directory
    jsonl_files = sorted(input_dir.glob("*.jsonl"))
    
    if not jsonl_files:
        click.echo(f"No JSONL files found in {input_dir}", err=True)
        return
    
    # Filter by resource if specified
    if chosen_resources:
        # Match JSONL files to requested resources by slugified filename
        resource_slugs = {slugify(r): r for r in chosen_resources}
        matched_files = []
        
        for jsonl_file in jsonl_files:
            file_slug = jsonl_file.stem  # filename without .jsonl
            # Try exact match first, then slugified match
            if file_slug in resource_slugs:
                matched_files.append((jsonl_file, resource_slugs[file_slug]))
            elif slugify(file_slug) in resource_slugs:
                matched_files.append((jsonl_file, resource_slugs[slugify(file_slug)]))
        
        if not matched_files:
            click.echo(
                f"No JSONL files found matching requested resources: {', '.join(chosen_resources)}",
                err=True,
            )
            return
    else:
        # Convert all JSONL files - try to infer resource name from filename
        # For common resources, map filename to resource name
        resource_map = {
            "immport": "ImmPort",
            "vdjserver": "VDJServer",
            "vivli": "Vivli",
            "radx_data_hub": "RADx Data Hub",
            "protein_data_bank": "Protein Data Bank",
            "project_tycho": "Project Tycho",
        }
        
        matched_files = []
        for jsonl_file in jsonl_files:
            file_slug = jsonl_file.stem
            resource_name = resource_map.get(file_slug, file_slug.replace("_", " ").title())
            matched_files.append((jsonl_file, resource_name))
    
    # Convert each file
    for jsonl_file, resource_name in matched_files:
        output_file = output_dir / f"{jsonl_file.stem}.nt"
        
        try:
            click.echo(f"Converting {jsonl_file.name} ({resource_name})...")
            count = convert_jsonl_to_rdf(
                input_path=jsonl_file,
                output_path=output_file,
                resource=resource_name,
            )
            click.echo(f"Converted {count} datasets to {output_file}")
        except Exception as exc:
            click.echo(f"Failed to convert {jsonl_file.name}: {exc}", err=True)
            continue


def main() -> None:  # pragma: no cover
    cli()


if __name__ == "__main__":  # pragma: no cover
    main()

