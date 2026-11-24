"""Deploy-time model package fetch (opt-in) for hosts with an ephemeral disk (e.g. Render free).

Model files are never committed to Git. When MODEL_PACKAGE_URL and MODEL_PACKAGE_SHA256 are
set, `scripts/fetch_model.py` downloads the packaged model (a zip holding package.json,
model.onnx and optionally cam_weights.npy), verifies the archive SHA-256 *and* the artefact
checksum recorded in package.json, and installs it under MODEL_PATH/<name>/<version>/.
Without those settings nothing happens and Crop Doctor keeps reporting model_unavailable.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ALLOWED = frozenset({"model.onnx", "cam_weights.npy", "package.json"})
MAX_BYTES = 200 * 1024 * 1024


class PackageError(Exception):
    """The package could not be fetched or failed verification (nothing was installed)."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def download(url: str, dest: Path, max_bytes: int = MAX_BYTES, timeout_s: float = 60) -> None:
    if not url.startswith("https://"):
        raise PackageError("MODEL_PACKAGE_URL must be an https:// URL")
    # https-only is checked above, so the S310 scheme warning does not apply.
    req = urllib.request.Request(url, headers={"User-Agent": "agrios-model-fetch"})  # noqa: S310
    total = 0
    with urllib.request.urlopen(req, timeout=timeout_s) as resp, dest.open("wb") as fh:  # noqa: S310
        while chunk := resp.read(1 << 20):
            total += len(chunk)
            if total > max_bytes:
                raise PackageError(f"package is larger than {max_bytes} bytes")
            fh.write(chunk)


def extract(zip_path: Path, out_dir: Path) -> dict:
    """Extract only the allowed file names (folders flattened, no path traversal) and verify."""
    seen: set[str] = set()
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                name = PurePosixPath(info.filename.replace("\\", "/")).name
                if info.is_dir() or name not in ALLOWED:
                    continue
                if name in seen:
                    raise PackageError(f"duplicate {name} in package")
                if info.file_size > MAX_BYTES:
                    raise PackageError(f"{name} is too large")
                seen.add(name)
                with zf.open(info) as src, (out_dir / name).open("wb") as dst:
                    shutil.copyfileobj(src, dst)
    except zipfile.BadZipFile as exc:
        raise PackageError("package is not a valid zip archive") from exc
    if "package.json" not in seen:
        raise PackageError("package.json missing from the package")
    pkg = json.loads((out_dir / "package.json").read_text(encoding="utf-8"))
    artifact = pkg.get("artifact")
    if artifact not in ALLOWED or artifact not in seen:
        raise PackageError("package artefact missing")
    if sha256_file(out_dir / artifact) != pkg.get("checksum_sha256"):
        raise PackageError("artefact checksum does not match package.json")
    return pkg


def fetch_and_install(url: str, expected_sha256: str, model_root: Path) -> tuple[dict, str, bool]:
    """Returns (package.json, artifact uri relative to model_root, newly_installed)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        archive = tmp_dir / "package.zip"
        download(url, archive)
        if sha256_file(archive) != expected_sha256.strip().lower():
            raise PackageError("archive SHA-256 does not match MODEL_PACKAGE_SHA256")
        staged = tmp_dir / "pkg"
        staged.mkdir()
        pkg = extract(archive, staged)
        rel = f"{pkg['name']}/{pkg['version']}"
        uri = f"{rel}/{pkg['artifact']}"
        dest = model_root / rel
        installed = dest / pkg["artifact"]
        if installed.is_file() and sha256_file(installed) == pkg["checksum_sha256"]:
            return pkg, uri, False
        dest.mkdir(parents=True, exist_ok=True)
        for f in staged.iterdir():
            shutil.copy2(f, dest / f.name)
        return pkg, uri, True
