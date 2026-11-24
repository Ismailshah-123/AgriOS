import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from app.mlops import package_fetch as pf

ONNX = b"fake-onnx-bytes"


def _pkg(artifact_bytes: bytes = ONNX, **over: object) -> dict:
    pkg = {
        "name": "crop_doctor_tomato",
        "version": "1.0.0",
        "artifact": "model.onnx",
        "checksum_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
    }
    pkg.update(over)
    return pkg


def _zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def test_extract_verifies_and_flattens_folders(tmp_path: Path) -> None:
    z = _zip(
        tmp_path / "p.zip",
        {
            "1.0.0/package.json": json.dumps(_pkg()).encode(),
            "1.0.0/model.onnx": ONNX,
            "../../evil.py": b"print('x')",
            "notes.txt": b"ignored",
        },
    )
    out = tmp_path / "out"
    out.mkdir()
    pkg = pf.extract(z, out)
    assert pkg["name"] == "crop_doctor_tomato"
    assert sorted(p.name for p in out.iterdir()) == ["model.onnx", "package.json"]
    assert not (tmp_path / "evil.py").exists()


def test_extract_rejects_checksum_mismatch(tmp_path: Path) -> None:
    z = _zip(
        tmp_path / "p.zip",
        {"package.json": json.dumps(_pkg()).encode(), "model.onnx": b"tampered"},
    )
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(pf.PackageError, match="checksum"):
        pf.extract(z, out)


@pytest.mark.parametrize(
    "members",
    [
        {"model.onnx": ONNX},  # no package.json
        {"package.json": json.dumps(_pkg(artifact="../x.onnx")).encode(), "model.onnx": ONNX},
    ],
)
def test_extract_rejects_incomplete_packages(tmp_path: Path, members: dict[str, bytes]) -> None:
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(pf.PackageError):
        pf.extract(_zip(tmp_path / "p.zip", members), out)


def test_extract_rejects_non_zip(tmp_path: Path) -> None:
    bad = tmp_path / "p.zip"
    bad.write_bytes(b"not a zip")
    with pytest.raises(pf.PackageError, match="zip"):
        pf.extract(bad, tmp_path)


def test_download_requires_https(tmp_path: Path) -> None:
    with pytest.raises(pf.PackageError, match="https"):
        pf.download("http://example.test/p.zip", tmp_path / "p.zip")


def _fake_download(src: Path):
    def fake(url: str, dest: Path, *a: object, **k: object) -> None:
        dest.write_bytes(src.read_bytes())

    return fake


def test_fetch_and_install_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = _zip(
        tmp_path / "src.zip", {"package.json": json.dumps(_pkg()).encode(), "model.onnx": ONNX}
    )
    sha = pf.sha256_file(src)
    monkeypatch.setattr(pf, "download", _fake_download(src))
    root = tmp_path / "models"
    pkg, uri, fresh = pf.fetch_and_install("https://h.test/p.zip", sha.upper(), root)
    assert fresh and uri == "crop_doctor_tomato/1.0.0/model.onnx"
    assert (root / uri).read_bytes() == ONNX
    assert pf.fetch_and_install("https://h.test/p.zip", sha, root)[2] is False


def test_fetch_and_install_rejects_wrong_archive_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = _zip(
        tmp_path / "src.zip", {"package.json": json.dumps(_pkg()).encode(), "model.onnx": ONNX}
    )
    monkeypatch.setattr(pf, "download", _fake_download(src))
    root = tmp_path / "models"
    with pytest.raises(pf.PackageError, match="SHA-256"):
        pf.fetch_and_install("https://h.test/p.zip", "0" * 64, root)
    assert not root.exists()
