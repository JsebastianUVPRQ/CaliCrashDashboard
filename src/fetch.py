"""Download official Cali open-data sources from the CKAN portal.

The Secretaría de Movilidad publishes its accident and fatality datasets on
``datos.cali.gov.co`` (CKAN API). This module downloads the three resources
that feed the dashboard, tracking lineage in ``data/raw/manifiesto_linaje.json``
so files are only re-downloaded when the remote version changes.

Sources:
- Siniestralidad 2016-2024 (crash records reported by transit agents).
- Lesionados 2016-2025 (injured people register; by design only "Con lesionado").
- Consolidado de muertes en accidentes de tránsito 2016-2023 (fatalities by
  person: sex, age, hour, event date, death date and road-user condition).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import urllib.error
import urllib.request
from pathlib import Path

CKAN_API = "https://datos.cali.gov.co/api/3/action"
RAW_DIR = Path("data/raw")
FATALITY_DIR = Path("data/fallecidos")
MANIFEST_PATH = Path("data/raw/manifiesto_linaje.json")

CHUNK_SIZE = 1024 * 512
HTTP_TIMEOUT = 120


@dataclass(frozen=True)
class CkanSource:
    """A downloadable CKAN dataset resource."""

    label: str
    package_id: str
    resource_id: str
    out_path: Path


SOURCES: tuple[CkanSource, ...] = (
    CkanSource(
        label="Siniestralidad 2016-2024",
        package_id="cb62a408-9029-4331-8815-ca2caeb126c0",
        resource_id="e0572389-cc41-4c1f-b443-862be10b6cc3",
        out_path=RAW_DIR / "cali_siniestralidad_2016_2024.csv",
    ),
    CkanSource(
        label="Lesionados 2016-2025",
        package_id="75c089ba-7df3-4816-b80f-c69c6e5362ae",
        resource_id="b5e009ef-8739-487d-bb0a-ffab613ce5cb",
        out_path=RAW_DIR / "cali_lesionados_2016_2025.csv",
    ),
    CkanSource(
        label="Consolidado de muertes 2016-2023",
        package_id="eeb7508e-1b84-4582-9676-43cf5d6ce443",
        resource_id="8629eb9b-10e2-464c-a4ac-87fa9efc453a",
        out_path=FATALITY_DIR / "cali_muertes_2016_2023.csv",
    ),
)


def load_manifest() -> dict:
    """Load the lineage manifest or return an empty mapping."""
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest: dict) -> None:
    """Persist the lineage manifest as pretty JSON."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def resource_show(resource_id: str) -> dict:
    """Return CKAN resource metadata (URL, last_modified, size...)."""
    url = f"{CKAN_API}/resource_show?id={resource_id}"
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("success"):
        raise RuntimeError(f"CKAN resource_show falló para {resource_id}")
    return payload["result"]


def sha256_of_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a local file."""
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_to(url: str, out_path: Path) -> None:
    """Stream a file from ``url`` into ``out_path`` (atomic-ish: temp first)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = out_path.with_suffix(out_path.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "cali-crash-dashboard"})
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response, temp_path.open(
        "wb"
    ) as handle:
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            handle.write(chunk)
    temp_path.replace(out_path)


def fetch_source(
    source: CkanSource,
    manifest: dict,
    *,
    force: bool = False,
) -> bool:
    """Download ``source`` if its remote version changed.

    Args:
        source: CKAN resource descriptor.
        manifest: Lineage manifest (mutated in place on success).
        force: Re-download even if the manifest says it is unchanged.

    Returns:
        True when the file was downloaded, False when it was skipped
        because the local snapshot already matches the remote version.
    """
    meta = resource_show(source.resource_id)
    url = meta["url"]
    last_modified = meta.get("last_modified") or meta.get("metadata_modified") or ""
    record = manifest.setdefault(source.resource_id, {})
    known = record.get("sha256")
    known_modified = record.get("last_modified", "")

    if (
        not force
        and source.out_path.exists()
        and known == sha256_of_file(source.out_path)
        and known_modified == last_modified
    ):
        print(f"[skip] {source.label}: sin cambios desde {known_modified}")
        return False

    print(f"[get]  {source.label}: {url}")
    download_to(url, source.out_path)
    record.update(
        {
            "label": source.label,
            "url": url,
            "last_modified": last_modified,
            "sha256": sha256_of_file(source.out_path),
            "size_bytes": source.out_path.stat().st_size,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )
    return True


def fetch_all(*, force: bool = False) -> dict:
    """Download every configured source and return the updated manifest."""
    manifest = load_manifest()
    for source in SOURCES:
        fetch_source(source, manifest, force=force)
    save_manifest(manifest)
    return manifest
