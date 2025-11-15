from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, Iterable, List, Optional

import click
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://api.data.niaid.nih.gov/v1/query"
DEFAULT_PAGE_SIZE = 100
DEFAULT_FACET_SIZE = 10
DEFAULT_SEGMENT_FIELD = "identifier"
DEFAULT_SEGMENT_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DEFAULT_MAX_PREFIX_LENGTH = 4
MAX_RESULT_WINDOW = 10_000
DEFAULT_RESOURCES = (
    "ImmPort",
    "VDJServer",
    "Vivli",
    "RADx Data Hub",
    "PDB",
    "Project Tycho",
)


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
        backoff_factor=1.0,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=("GET",),
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
) -> dict:
    params = {
        "q": query,
        "extra_filter": extra_filter,
        "facet_size": facet_size,
        "size": size,
    }
    if offset:
        params["from"] = offset
    response = session.get(BASE_URL, params=params)
    response.raise_for_status()
    return response.json()


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

        if prefix_total <= max_window or depth >= max_prefix_length:
            if depth >= max_prefix_length and prefix_total > max_window:
                click.echo(
                    f"Warning: prefix '{prefix}' reached max depth with {prefix_total} records; "
                    "requests may still hit the window limit.",
                    err=True,
                )
            segments.append({"prefix": prefix, "total": prefix_total})
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
            state.segments = compute_segments(
                session=session,
                extra_filter=extra_filter,
                facet_size=facet_size,
                segment_field=segment_field,
                charset=segment_charset,
                max_window=max_window,
                max_prefix_length=segment_max_length,
            )
            state.segment_index = 0
            state.segment_offset = 0
            state.dump(state_path)
    elif state.mode == "segmented" and not state.segments:
        state.segments = compute_segments(
            session=session,
            extra_filter=extra_filter,
            facet_size=facet_size,
            segment_field=segment_field,
            charset=segment_charset,
            max_window=max_window,
            max_prefix_length=segment_max_length,
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

        while offset < segment_total:
            size = min(page_size, segment_total - offset)
            payload = request_payload(
                session=session,
                extra_filter=extra_filter,
                facet_size=facet_size,
                size=size,
                offset=offset,
                query=build_query(prefix, segment_field),
            )
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
) -> None:
    """Fetch dataset records from the NIAID API for one or more resources."""
    chosen_resources = tuple(resources) or ("ImmPort",)
    session = configure_session()

    if not segment_field.strip():
        raise click.BadParameter("segment-field must not be empty.", param_name="segment_field")
    if not segment_charset:
        raise click.BadParameter("segment-charset must not be empty.", param_name="segment_charset")
    segment_charset = "".join(dict.fromkeys(segment_charset))

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
        except requests.HTTPError as exc:  # pragma: no cover
            click.echo(f"Failed to fetch {resource!r}: {exc}", err=True)
            break


def main() -> None:  # pragma: no cover
    cli()


if __name__ == "__main__":  # pragma: no cover
    main()

