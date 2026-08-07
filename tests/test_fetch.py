"""Tests for the CKAN lineage fetcher (no network required)."""

import src.fetch as fetch


def _source(tmp_path, resource_id: str = "res-1") -> fetch.CkanSource:
    return fetch.CkanSource(
        label="test",
        package_id="pkg-1",
        resource_id=resource_id,
        out_path=tmp_path / (resource_id + ".csv"),
    )


def test_sha256_of_file_is_stable_and_unique(tmp_path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first.write_bytes(b"contenido A")
    second.write_bytes(b"contenido B")

    assert fetch.sha256_of_file(first) == fetch.sha256_of_file(first)
    assert fetch.sha256_of_file(first) != fetch.sha256_of_file(second)


def test_manifest_roundtrip(tmp_path, monkeypatch) -> None:
    manifest_path = tmp_path / "manifiesto.json"
    monkeypatch.setattr(fetch, "MANIFEST_PATH", manifest_path)

    fetch.save_manifest({"res-1": {"sha": "abc"}})
    loaded = fetch.load_manifest()

    assert loaded == {"res-1": {"sha": "abc"}}


def test_load_manifest_missing_is_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fetch, "MANIFEST_PATH", tmp_path / "no_existe.json")

    assert fetch.load_manifest() == {}


def test_fetch_source_skips_unchanged(tmp_path, monkeypatch) -> None:
    source = _source(tmp_path)
    source.out_path.write_bytes(b"cargado")
    manifest = {
        source.resource_id: {
            "sha256": fetch.sha256_of_file(source.out_path),
            "last_modified": "2024-01-01T00:00:00",
        }
    }
    monkeypatch.setattr(
        fetch,
        "resource_show",
        lambda _rid: {"url": "http://example.test/d", "last_modified": "2024-01-01T00:00:00"},
    )

    def _fail_download(*_args, **_kwargs):  # pragma: no cover
        raise AssertionError("no debería descargar")

    monkeypatch.setattr(fetch, "download_to", _fail_download)

    assert fetch.fetch_source(source, manifest) is False
    assert source.out_path.read_bytes() == b"cargado"


def test_fetch_source_downloads_when_remote_changed(tmp_path, monkeypatch) -> None:
    source = _source(tmp_path)
    source.out_path.write_bytes(b"viejo")
    manifest = {source.resource_id: {"sha256": fetch.sha256_of_file(source.out_path)}}
    monkeypatch.setattr(
        fetch,
        "resource_show",
        lambda _rid: {"url": "https://example.test/nuevo", "last_modified": "2025-01-01T00:00:00"},
    )
    monkeypatch.setattr(
        fetch,
        "download_to",
        lambda _url, out_path: out_path.write_bytes(b"nuevo"),
    )

    assert fetch.fetch_source(source, manifest) is True
    assert source.out_path.read_bytes() == b"nuevo"
    assert manifest[source.resource_id]["sha256"] == fetch.sha256_of_file(source.out_path)
    assert manifest[source.resource_id]["label"] == source.label


def test_fetch_source_force_redownloads(tmp_path, monkeypatch) -> None:
    source = _source(tmp_path)
    source.out_path.write_bytes(b"cargado")
    manifest = {
        source.resource_id: {
            "sha256": fetch.sha256_of_file(source.out_path),
            "last_modified": "2024-01-01T00:00:00",
        }
    }
    monkeypatch.setattr(
        fetch,
        "resource_show",
        lambda _rid: {"url": "https://example.test/d", "last_modified": "2024-01-01T00:00:00"},
    )
    monkeypatch.setattr(
        fetch,
        "download_to",
        lambda _url, out_path: out_path.write_bytes(b"refresco"),
    )

    assert fetch.fetch_source(source, manifest, force=True) is True
    assert source.out_path.read_bytes() == b"refresco"