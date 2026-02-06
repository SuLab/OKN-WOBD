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
DEFAULT_MAX_PREFIX_LENGTH = 8
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
    segment_field: Optional[str] = None  # Track which field was used for segmentation

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
            segment_field=payload.get("segment_field"),
        )

    def dump(self, path: Path) -> None:
        payload = {
            "resource": self.resource,
            "mode": self.mode,
            "segment_field": self.segment_field,
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
    non_dataset_repositories = []
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
            # Prioritize identifier over name, as identifier matches what's in dataset records
            source_name = info.get("identifier") or info.get("name") or key
            
            # Check if excluded
            if source_name in excluded_set:
                excluded_resources.append({
                    "name": source_name,
                    "reason": "explicitly excluded",
                    "has_datasets": False,
                })
                continue
            
            # Filter out Non-Dataset Repositories (e.g., Computational Tool Repositories)
            source_type = info.get("type", "")
            if source_type == "Computational Tool Repository":
                non_dataset_repositories.append({
                    "name": source_name,
                    "type": source_type,
                    "reason": "Not a Dataset Repository",
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
        click.echo(f"  Filtered out {len(non_dataset_repositories)} non-dataset repositories")
        click.echo(f"  Skipped {len(sources_without_datasets)} sources (no datasets)")
        
        # Save excluded resources log file to default reports directory
        log_dir = Path("reports")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "excluded_resources_log.json"
        
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "excluded_resources": excluded_resources,
            "non_dataset_repositories": non_dataset_repositories,
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


def build_query(prefix: str, segment_field: str, wildcard_query: Optional[str] = None) -> str:
    """Build a query string for the given prefix.
    
    Handles both normal prefix queries and wildcard queries for special cases.
    For prefixes like "DRYAD.0", creates a wildcard query like "*dryad.0*"
    to match identifiers like "doi:10.5061/dryad.0XXXX".
    For _id field with wildcard prefixes, uses the provided wildcard_query if available.
    """
    # If a wildcard_query was provided (from segment dict), use it directly
    if wildcard_query:
        return wildcard_query
    
    if not prefix:
        return "*"
    
    # Check if this is a wildcard prefix for _id field (format: "PREFIX.CHAR" where PREFIX is like "NCBI_SRA")
    # These are created by the _id wildcard segmentation logic
    if segment_field == "_id" and "." in prefix:
        parts = prefix.split(".", 1)
        if len(parts) == 2:
            base, char = parts
            # Reconstruct the wildcard query pattern
            # Base like "NCBI_SRA" should become "ncbi_sra"
            base_lower = base.lower()
            # Handle common patterns
            if base_lower.startswith("ncbi"):
                base_lower = "ncbi_sra"
            elif base_lower.startswith("sra") and len(base_lower) == 3:
                base_lower = "sra"
            return f"_id:*{base_lower}_{char.lower()}*"
    
    # Check if this is a name-based segmentation prefix (format: "NAME_CHAR" or "NAME_CHAR1CHAR2")
    if segment_field == "name" and prefix.startswith("NAME_"):
        name_chars = prefix.replace("NAME_", "").lower()
        return f"name:{name_chars}*"
    
    # Check if this is a date-based segmentation prefix (format: "DATE_YYYY" or "DATE_YYYY_MM")
    if segment_field == "date" and prefix.startswith("DATE_"):
        date_part = prefix.replace("DATE_", "")
        if "_" in date_part:
            # Format: DATE_YYYY_MM
            year, month = date_part.split("_", 1)
            return f"date:{year}-{month}*"
        else:
            # Format: DATE_YYYY
            return f"date:{date_part}*"
    
    # Check if this is a wildcard prefix (contains a dot, indicating suffix segmentation)
    # e.g., "DRYAD.0" should become "*dryad.0*"
    if "." in prefix and prefix.upper().startswith(("DRYAD", "DOI")):
        # Extract the base and suffix parts
        parts = prefix.split(".", 1)
        if len(parts) == 2:
            base, suffix = parts
            # Create wildcard query to match the suffix part
            return f"{segment_field}:*{base.lower()}.{suffix}*"
    
    # Normal prefix query
    return f"{segment_field}:{prefix}*"


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
) -> tuple[List[dict], str]:
    total = query_total(
        session=session,
        extra_filter=extra_filter,
        facet_size=facet_size,
        query=build_query("", segment_field),
    )
    if total <= max_window:
        return [{"prefix": "", "total": total}], segment_field

    segments: List[dict] = []
    pending: Deque[tuple[str, int, int]] = deque()
    seen: set[str] = set()

    pending.append(("", total, 0))
    seen.add("")

    click.echo(f"Computing segments (total records: {total:,})...")
    processed_count = 0
    queue_size_logged = False
    
    # Track if we found any children for the empty prefix - if not, the field might not exist
    empty_prefix_children_found = False

    while pending:
        prefix, prefix_total, depth = pending.popleft()
        processed_count += 1

        if prefix_total == 0:
            continue

        # API limit: from + size <= max_window, so we need segments with total < max_window
        # Use max_window - 1 as the safe limit to ensure we can always fetch all records
        safe_limit = max_window - 1
        
        if prefix_total <= safe_limit:
            segments.append({"prefix": prefix, "total": prefix_total})
            if processed_count % 50 == 0:
                click.echo(f"  Processed {processed_count} prefixes, found {len(segments)} segments, {len(pending)} in queue...")
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

        # Log when processing important prefixes for debugging
        if prefix in ("D", "DR", "DRY") or (prefix.startswith("DR") and len(prefix) <= 4):
            click.echo(f"  Processing prefix '{prefix}' ({prefix_total:,} records, depth {depth}, queue size: {len(pending)})...")
        
        # Track if we found any children during sub-segmentation
        children_found = False
        for char in charset:
            child_prefix = prefix + char
            if child_prefix in seen:
                continue

            try:
                child_total = query_total(
                    session=session,
                    extra_filter=extra_filter,
                    facet_size=facet_size,
                    query=build_query(child_prefix, segment_field),
                )
                seen.add(child_prefix)
                if child_total:
                    children_found = True
                    if prefix == "":
                        empty_prefix_children_found = True
                    pending.append((child_prefix, child_total, depth + 1))
                    # Log when adding important prefixes to queue
                    if child_prefix in ("DR", "DRY", "DRYA") or (child_prefix.startswith("DR") and len(child_prefix) <= 5):
                        click.echo(f"    Added '{child_prefix}' to queue ({child_total:,} records)")
            except Exception as e:
                click.echo(
                    f"Error querying prefix '{child_prefix}': {e}. Continuing with other prefixes...",
                    err=True,
                )
                seen.add(child_prefix)  # Mark as seen to avoid retrying
                # Continue processing other prefixes instead of failing completely
        
        # If we tried to sub-segment the empty prefix but found no children, try date-based segmentation
        # This handles cases where records don't have an 'identifier' field and _id doesn't support prefix queries
        # (e.g., NCBI SRA uses _id but API doesn't support prefix queries on it)
        if not children_found and prefix == "" and prefix_total > safe_limit and segment_field == "identifier":
            click.echo(f"  No children found for empty prefix with '{segment_field}' field. Trying date-based segmentation...")
            # Try date-based segmentation as fallback
            # Segment by year ranges
            date_segments = []
            years = list(range(2010, 2026))  # Common date range for datasets
            date_children_found = False
            
            for year in years:
                try:
                    # Try different date query formats
                    # Format 1: date:2023*
                    date_query = f"date:{year}*"
                    year_total = query_total(
                        session=session,
                        extra_filter=extra_filter,
                        facet_size=facet_size,
                        query=date_query,
                    )
                    # If that doesn't work, try dateModified or datePublished
                    if year_total == 0:
                        date_query = f"dateModified:{year}*"
                        year_total = query_total(
                            session=session,
                            extra_filter=extra_filter,
                            facet_size=facet_size,
                            query=date_query,
                        )
                    if year_total == 0:
                        date_query = f"datePublished:{year}*"
                        year_total = query_total(
                            session=session,
                            extra_filter=extra_filter,
                            facet_size=facet_size,
                            query=date_query,
                        )
                    
                    if year_total > 0:
                        date_children_found = True
                        date_segments.append({
                            "prefix": f"DATE_{year}",
                            "total": year_total,
                            "wildcard_query": date_query
                        })
                        click.echo(f"    Found date segment '{year}': {year_total:,} records")
                except Exception:
                    continue
            
            # If date segmentation found segments, use it
            if date_children_found and date_segments:
                # Check if we need to sub-segment any year segments that exceed the limit
                final_segments = []
                for seg in date_segments:
                    if seg["total"] <= safe_limit:
                        final_segments.append(seg)
                    else:
                        # Try to sub-segment by month for this year
                        year = seg["prefix"].replace("DATE_", "")
                        months_found = False
                        for month in range(1, 13):
                            try:
                                month_query = f"date:{year}-{month:02d}*"
                                month_total = query_total(
                                    session=session,
                                    extra_filter=extra_filter,
                                    facet_size=facet_size,
                                    query=month_query,
                                )
                                if month_total > 0:
                                    months_found = True
                                    final_segments.append({
                                        "prefix": f"DATE_{year}_{month:02d}",
                                        "total": month_total,
                                        "wildcard_query": month_query
                                    })
                            except Exception:
                                continue
                        if not months_found:
                            # If month segmentation didn't work, cap the year segment
                            final_segments.append({
                                "prefix": seg["prefix"],
                                "total": safe_limit,
                                "wildcard_query": seg["wildcard_query"]
                            })
                
                if final_segments:
                    click.echo(f"  Found {len(final_segments)} segments using date-based segmentation.")
                    return final_segments, "date"
            
            # If date segmentation didn't work, try name-based segmentation
            if not date_children_found and prefix == "" and prefix_total > safe_limit and segment_field == "identifier":
                click.echo(f"  Date-based segmentation failed. Trying 'name' field segmentation...")
                # Try name-based segmentation as another fallback
                # Segment by name prefixes (first character)
                name_segments = []
                name_children_found = False
                
                for char in charset:
                    try:
                        name_query = f"name:{char}*"
                        name_total = query_total(
                            session=session,
                            extra_filter=extra_filter,
                            facet_size=facet_size,
                            query=name_query,
                        )
                        if name_total > 0:
                            name_children_found = True
                            name_segments.append({
                                "prefix": f"NAME_{char.upper()}",
                                "total": name_total,
                                "wildcard_query": name_query
                            })
                            click.echo(f"    Found name segment '{char}': {name_total:,} records")
                    except Exception:
                        continue
                
                if name_children_found and name_segments:
                    # Check if we need to sub-segment any name segments that exceed the limit
                    final_name_segments = []
                    for seg in name_segments:
                        if seg["total"] <= safe_limit:
                            final_name_segments.append(seg)
                        else:
                            # Try to sub-segment by second character
                            prefix_char = seg["prefix"].replace("NAME_", "")
                            sub_segmented = False
                            for char2 in charset:
                                try:
                                    sub_query = f"name:{prefix_char.lower()}{char2}*"
                                    sub_total = query_total(
                                        session=session,
                                        extra_filter=extra_filter,
                                        facet_size=facet_size,
                                        query=sub_query,
                                    )
                                    if sub_total > 0:
                                        sub_segmented = True
                                        final_name_segments.append({
                                            "prefix": f"NAME_{prefix_char}{char2.upper()}",
                                            "total": sub_total,
                                            "wildcard_query": sub_query
                                        })
                                except Exception:
                                    continue
                            if not sub_segmented:
                                # If sub-segmentation didn't work, cap the segment
                                final_name_segments.append({
                                    "prefix": seg["prefix"],
                                    "total": safe_limit,
                                    "wildcard_query": seg["wildcard_query"]
                                })
                    
                    if final_name_segments:
                        click.echo(f"  Found {len(final_name_segments)} segments using name-based segmentation.")
                        return final_name_segments, "name"
        
        # If we tried to sub-segment but found no children, try wildcard segmentation
        # This handles cases where prefix matching doesn't work for deeper levels
        # (e.g., identifiers like "doi:10.5061/dryad.XXXXX" where "DRYAD" matches all but children don't)
        if not children_found and prefix_total > safe_limit:
            # Try wildcard segmentation: for patterns like "doi:10.5061/dryad.XXXXX",
            # try segmenting on the suffix part using wildcards
            wildcard_children_found = False
            if prefix.upper() in ("DRYAD", "DOI") and depth < max_prefix_length:
                # Try wildcard queries for the suffix part (e.g., *dryad.0*, *dryad.1*, etc.)
                click.echo(f"    Trying wildcard segmentation for '{prefix}'...")
                for char in charset:
                    # Use wildcard to match the suffix part after the dot
                    wildcard_query = f"{segment_field}:*{prefix.lower()}.{char}*"
                    try:
                        child_total = query_total(
                            session=session,
                            extra_filter=extra_filter,
                            facet_size=facet_size,
                            query=wildcard_query,
                        )
                        if child_total:
                            wildcard_children_found = True
                            wildcard_prefix = f"{prefix}.{char}"
                            if wildcard_prefix not in seen:
                                seen.add(wildcard_prefix)
                                pending.append((wildcard_prefix, child_total, depth + 1))
                                click.echo(f"    Added '{wildcard_prefix}' (wildcard) to queue ({child_total:,} records)")
                    except Exception as e:
                        # Continue trying other characters
                        continue
            
            # If wildcard segmentation also failed, add as capped segment
            if not wildcard_children_found:
                warning_msg = (
                    f"prefix '{prefix}' exceeds safe limit ({safe_limit}) but sub-segmentation found no children. "
                    f"Adding as capped segment. Some records may not be fetchable."
                )
                click.echo(f"Warning: {warning_msg}", err=True)
                if warnings is not None:
                    warnings.append({
                        "type": "no_children_found",
                        "prefix": prefix,
                        "depth": depth,
                        "record_count": prefix_total,
                        "safe_limit": safe_limit,
                        "message": warning_msg,
                    })
                segments.append({"prefix": prefix, "total": safe_limit})

    # Verify segments sum matches total
    segment_sum = sum(s.get("total", 0) for s in segments)
    missing = total - segment_sum
    if segment_sum < total * 0.9:  # Allow 10% tolerance for capped segments
        click.echo(
            f"Warning: Segment total ({segment_sum:,}) is significantly less than "
            f"expected total ({total:,}). Missing {missing:,} records.",
            err=True,
        )
        click.echo(
            f"  This suggests some prefixes were not explored during segmentation. "
            f"Consider checking for prefixes that should have been sub-segmented.",
            err=True,
        )

    click.echo(f"  Computed {len(segments)} segments from {processed_count} prefixes.")
    segments.sort(key=lambda item: item["prefix"])
    return segments or [{"prefix": "", "total": total}], segment_field


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
            state.segments, actual_segment_field = compute_segments(
                session=session,
                extra_filter=extra_filter,
                facet_size=facet_size,
                segment_field=segment_field,
                charset=segment_charset,
                max_window=max_window,
                max_prefix_length=segment_max_length,
                warnings=resource_warnings,
            )
            state.segment_field = actual_segment_field
            state.segment_index = 0
            state.segment_offset = 0
            state.dump(state_path)
    elif state.mode == "segmented" and not state.segments:
        # Collect warnings during segmentation
        state.segments, actual_segment_field = compute_segments(
            session=session,
            extra_filter=extra_filter,
            facet_size=facet_size,
            segment_field=segment_field,
            charset=segment_charset,
            max_window=max_window,
            max_prefix_length=segment_max_length,
            warnings=resource_warnings,
        )
        state.segment_field = actual_segment_field
        state.dump(state_path)
    
    with data_path.open("a", encoding="utf-8") as data_file:
        if state.mode == "segmented":
            # Use the segment_field from state if available (may have been switched to _id)
            actual_segment_field = state.segment_field or segment_field
            fetch_segmented(
                session=session,
                data_file=data_file,
                state_path=state_path,
                state=state,
                page_size=page_size,
                facet_size=facet_size,
                extra_filter=extra_filter,
                segment_field=actual_segment_field,
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
    
    # Track seen identifiers to avoid duplicates
    seen_identifiers = set()
    duplicates_skipped = 0

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
                # Check if segment has a stored wildcard_query (for _id field segmentation)
                wildcard_query = segment.get("wildcard_query")
                query = build_query(prefix, segment_field, wildcard_query=wildcard_query)
                payload = request_payload(
                    session=session,
                    extra_filter=extra_filter,
                    facet_size=facet_size,
                    size=size,
                    offset=offset,
                    query=query,
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
                # Extract identifier for deduplication
                # Use identifier if available, otherwise fall back to _id
                identifier = item.get("identifier") or item.get("_id", "")
                
                # Skip if we've already seen this identifier
                if identifier in seen_identifiers:
                    duplicates_skipped += 1
                    continue
                
                # Mark as seen and write
                seen_identifiers.add(identifier)
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

    if duplicates_skipped > 0:
        click.echo(
            f"Skipped {duplicates_skipped} duplicate record(s) during fetch "
            f"for {state.resource!r}."
        )
    
    click.echo(f"Completed segmented fetch for {state.resource!r}.")


@click.group()
@click.option("--verbose", is_flag=True, help="Enable verbose logging.")
def cli(verbose: bool) -> None:
    """CLI utilities for working with the NIAID dataset API."""
    # Configure basic logging - can be overridden by commands that need file logging
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


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
        
        # Load excluded resources data if available
        excluded_log_file = log_dir / "excluded_resources_log.json"
        excluded_resources_data = None
        if excluded_log_file.exists():
            try:
                with excluded_log_file.open("r", encoding="utf-8") as f:
                    excluded_resources_data = json.load(f)
            except Exception:
                # If we can't read it, just continue without it
                pass
        
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
        
        # Add excluded resources data if available
        if excluded_resources_data:
            summary["excluded_resources"] = excluded_resources_data.get("excluded_resources", [])
            summary["non_dataset_repositories"] = excluded_resources_data.get("non_dataset_repositories", [])
            summary["sources_without_datasets"] = excluded_resources_data.get("sources_without_datasets", [])
            summary["total_sources_in_nde"] = excluded_resources_data.get("total_sources", 0)
            summary["dataset_repositories_found"] = excluded_resources_data.get("dataset_repositories_found", 0)
        
        with summary_file.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        
        # Also save as Markdown report
        report_file = log_dir / "fetch_summary.md"
        with report_file.open("w", encoding="utf-8") as f:
            f.write("# Fetch Summary\n\n")
            f.write(f"**Timestamp:** {summary['timestamp']}\n\n")
            f.write("## Overview\n\n")
            f.write(f"- **Total resources:** {summary['total_resources']}\n")
            f.write(f"- **✓ Completed:** {summary['completed']}\n")
            if incomplete_resources:
                f.write(f"- **⚠ Incomplete:** {len(incomplete_resources)}\n")
            if failed_resources:
                f.write(f"- **✗ Failed:** {len(failed_resources)}\n")
            f.write("\n")
            
            if completed_resources:
                f.write("## Completed Resources\n\n")
                for resource in completed_resources:
                    f.write(f"- {resource}\n")
                f.write("\n")
            
            if incomplete_resources:
                f.write("## Incomplete Resources\n\n")
                f.write("Run again with `--restart` to resume fetching.\n\n")
                for item in incomplete_resources:
                    f.write(f"- **{item['resource']}**: {item['fetched']:,}/{item['total']:,} records ")
                    f.write(f"({item['remaining']:,} remaining)\n")
                f.write("\n")
            
            if failed_resources:
                f.write("## Failed Resources\n\n")
                f.write("Check errors and retry manually.\n\n")
                for item in failed_resources:
                    f.write(f"- **{item['resource']}**: {item['error_type']}\n")
                f.write("\n")
            
            # Add excluded resources and sources without datasets if available
            if excluded_resources_data:
                excluded_resources = excluded_resources_data.get("excluded_resources", [])
                non_dataset_repositories = excluded_resources_data.get("non_dataset_repositories", [])
                sources_without_datasets = excluded_resources_data.get("sources_without_datasets", [])
                total_sources = excluded_resources_data.get("total_sources", 0)
                dataset_repositories_found = excluded_resources_data.get("dataset_repositories_found", 0)
                
                f.write("## NDE Dataset Repository Discovery\n\n")
                f.write(f"- **Total Dataset Repositories in NDE:** {total_sources}\n")
                f.write(f"- **Dataset Repositories found:** {dataset_repositories_found}\n")
                f.write(f"- **Resources fetched:** {len(chosen_resources)}\n")
                f.write("\n")
                
                if excluded_resources:
                    f.write("### Excluded Resources\n\n")
                    f.write("These resources are explicitly excluded from fetching.\n\n")
                    for item in excluded_resources:
                        f.write(f"- **{item['name']}**: {item['reason']}\n")
                    f.write("\n")
                
                if non_dataset_repositories:
                    f.write("### Non-Dataset Repositories\n\n")
                    f.write("These sources are returned by the API but are not Dataset Repositories (e.g., Computational Tool Repositories). They are automatically filtered out.\n\n")
                    for item in non_dataset_repositories:
                        f.write(f"- **{item['name']}**: {item.get('type', 'Unknown type')} - {item['reason']}\n")
                    f.write("\n")
                
                if sources_without_datasets:
                    f.write("### Sources Without Datasets\n\n")
                    f.write("These sources are registered in the NDE but do not have datasets.\n\n")
                    for item in sources_without_datasets:
                        f.write(f"- **{item['name']}**: {item['reason']}\n")
                    f.write("\n")
        
        click.echo("\n" + "=" * 60)
        click.echo("FETCH SUMMARY")
        click.echo("=" * 60)
        click.echo(f"Total resources: {len(chosen_resources)}")
        click.echo(f"✓ Completed: {len(completed_resources)}")
        if incomplete_resources:
            click.echo(f"⚠ Incomplete: {len(incomplete_resources)} (see details below)")
        if failed_resources:
            click.echo(f"✗ Failed: {len(failed_resources)} (see details below)")
        click.echo(f"\nDetailed summary saved to:")
        click.echo(f"  - JSON: {summary_file}")
        click.echo(f"  - Markdown: {report_file}")
        
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
@click.option(
    "--log-file",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Path to write conversion log file (includes warnings about bad URIs, etc.). "
        "If omitted, logs only appear in terminal."
    ),
)
def convert_command(
    input_dir: Path,
    output_dir: Path,
    resources: Iterable[str],
    log_file: Optional[Path],
) -> None:
    """Convert JSONL dataset files to RDF N-Triples format."""
    # Configure file logging if requested
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # Capture all levels in file
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        # Add to root logger so all modules log to file
        logging.getLogger().addHandler(file_handler)
        click.echo(f"Logging to file: {log_file}")
    
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
            click.echo(f"Successfully converted {count} datasets to {output_file}")
        except Exception as exc:
            # Only report as failure if conversion didn't complete at all
            click.echo(f"Failed to convert {jsonl_file.name}: {exc}", err=True)
            continue


# =============================================================================
# GXA command group
# =============================================================================


@cli.group("gxa")
def gxa_group() -> None:
    """Gene Expression Atlas (GXA) pipeline commands."""
    pass


@gxa_group.command("convert")
@click.option(
    "--data-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help="Directory containing GXA experiment subdirectories (*-gea/).",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("data/gxa_rdf"),
    show_default=True,
    help="Directory for output .ttl files.",
)
@click.option(
    "--experiment",
    type=str,
    default=None,
    help="Process a single experiment (e.g., E-GEOD-5305).",
)
@click.option(
    "--p-value",
    type=float,
    default=0.01,
    show_default=True,
    help="P-value threshold for DE and GSEA filtering.",
)
@click.option(
    "--max-genes",
    type=int,
    default=200,
    show_default=True,
    help="Maximum DE genes per assay.",
)
@click.option(
    "--max-terms",
    type=int,
    default=20,
    show_default=True,
    help="Maximum enriched terms per type per contrast.",
)
@click.option(
    "--no-gsea",
    is_flag=True,
    help="Skip GSEA/pathway enrichment extraction.",
)
def gxa_convert(
    data_dir: Path,
    output_dir: Path,
    experiment: Optional[str],
    p_value: float,
    max_genes: int,
    max_terms: int,
    no_gsea: bool,
) -> None:
    """Convert GXA experiment data to RDF Turtle files."""
    from okn_wobd.gxa.pipeline import run_gxa_rdf_pipeline

    run_gxa_rdf_pipeline(
        data_dir=data_dir,
        output_dir=output_dir,
        experiment=experiment,
        p_value_threshold=p_value,
        max_genes_per_assay=max_genes,
        max_terms_per_type=max_terms,
        include_gsea=not no_gsea,
    )


@gxa_group.command("fetch")
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    required=True,
    help="Directory to store downloaded experiment data.",
)
@click.option(
    "--prefix",
    type=str,
    default="E-GEOD",
    show_default=True,
    help="Experiment prefix filter for FTP listing.",
)
@click.option(
    "--experiment",
    type=str,
    default=None,
    help="Download a single experiment (e.g., E-GEOD-5305).",
)
@click.option(
    "--max-size",
    type=float,
    default=10.0,
    show_default=True,
    help="Maximum file size in MB to download.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="List files without downloading.",
)
def gxa_fetch(
    data_dir: Path,
    prefix: str,
    experiment: Optional[str],
    max_size: float,
    dry_run: bool,
) -> None:
    """Download GXA experiment data from the EBI FTP server."""
    from okn_wobd.gxa.downloader import GXADownloader

    downloader = GXADownloader(
        data_dir=data_dir,
        prefix=prefix,
        max_size_mb=max_size,
        dry_run=dry_run,
    )

    click.echo(f"GXA Downloader")
    click.echo(f"  Data directory: {data_dir}")
    click.echo(f"  Prefix: {prefix}")
    click.echo(f"  Max file size: {max_size} MB")
    if dry_run:
        click.echo("  Mode: DRY RUN")

    try:
        processed = downloader.run(single_experiment=experiment)
        click.echo(f"\nProcessed {processed} experiments.")
    except KeyboardInterrupt:
        click.echo("\nDownload interrupted. Progress has been saved.")
    except Exception as e:
        click.echo(f"\nDownload failed: {e}", err=True)


@gxa_group.command("run")
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    required=True,
    help="Directory for experiment data (download target and convert source).",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("data/gxa_rdf"),
    show_default=True,
    help="Directory for output .ttl files.",
)
@click.option(
    "--prefix",
    type=str,
    default="E-GEOD",
    show_default=True,
    help="Experiment prefix filter for FTP download.",
)
@click.option(
    "--experiment",
    type=str,
    default=None,
    help="Process a single experiment.",
)
@click.option(
    "--p-value",
    type=float,
    default=0.01,
    show_default=True,
    help="P-value threshold.",
)
@click.option(
    "--max-genes",
    type=int,
    default=200,
    show_default=True,
    help="Maximum DE genes per assay.",
)
@click.option(
    "--no-gsea",
    is_flag=True,
    help="Skip GSEA extraction.",
)
def gxa_run(
    data_dir: Path,
    output_dir: Path,
    prefix: str,
    experiment: Optional[str],
    p_value: float,
    max_genes: int,
    no_gsea: bool,
) -> None:
    """Fetch + convert in one step."""
    from okn_wobd.gxa.downloader import GXADownloader
    from okn_wobd.gxa.pipeline import run_gxa_rdf_pipeline

    # Step 1: Fetch
    click.echo("Step 1: Downloading GXA data...")
    downloader = GXADownloader(
        data_dir=data_dir,
        prefix=prefix,
    )
    downloader.run(single_experiment=experiment)

    # Step 2: Convert
    click.echo("\nStep 2: Converting to RDF...")
    run_gxa_rdf_pipeline(
        data_dir=data_dir,
        output_dir=output_dir,
        experiment=experiment,
        p_value_threshold=p_value,
        max_genes_per_assay=max_genes,
        include_gsea=not no_gsea,
    )


def main() -> None:  # pragma: no cover
    cli()


if __name__ == "__main__":  # pragma: no cover
    main()

