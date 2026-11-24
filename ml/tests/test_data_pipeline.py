import csv
import io
import json
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from agrios_ml.data import extract
from agrios_ml.data.imagestats import hamming, measure
from agrios_ml.data.splits import near_duplicate_pairs, stratified_group_split


def _jpg(seed: int, size: tuple[int, int] = (96, 80)) -> bytes:
    rng = np.random.default_rng(seed)
    arr = (rng.random((size[1] // 8, size[0] // 8, 3)) * 255).astype(np.uint8)
    im = Image.fromarray(arr).resize(size, Image.Resampling.BILINEAR)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def _zip(path: Path, members: dict[str, bytes]) -> str:
    with zipfile.ZipFile(path, "w") as z:
        for k, v in members.items():
            z.writestr(k, v)
    return extract.md5_file(path)


def test_safe_member_path_rejects_traversal() -> None:
    assert extract.safe_member_path("root/data/a.jpg", "root").as_posix() == "data/a.jpg"
    for bad in ("root/../x.jpg", "/root/a.jpg", "other/a.jpg", "root\\a.jpg", "C:/root/a.jpg"):
        assert extract.safe_member_path(bad, "root") is None


def test_extract_verifies_md5_rejects_bad_types_and_resumes(tmp_path: Path) -> None:
    arc = tmp_path / "a.zip"
    md5 = _zip(
        arc,
        {
            "root/data/c1/a.jpg": _jpg(1),
            "root/metadata.csv": b"x\n",
            "root/.cache/stub.metadata": b"s",
        },
    )
    dest, rec = tmp_path / "out", tmp_path / "rec.json"
    args = [
        "--archive",
        str(arc),
        "--dest",
        str(dest),
        "--root-prefix",
        "root",
        "--record",
        str(rec),
    ]
    assert extract.main([*args, "--expected-md5", "0" * 32]) == 3  # checksum mismatch
    assert extract.main([*args, "--expected-md5", md5]) == 0
    r = json.loads(rec.read_text())
    assert r["verified"] and r["written_this_run"] == 2 and r["skipped_members"] == 1
    assert not (dest / ".cache").exists()
    assert extract.main([*args, "--expected-md5", md5]) == 0  # resume: nothing rewritten
    assert json.loads(rec.read_text())["reused_existing"] == 2
    arc2 = tmp_path / "b.zip"
    md5b = _zip(arc2, {"root/data/evil.exe": b"MZ"})
    assert (
        extract.main(
            [
                "--archive",
                str(arc2),
                "--dest",
                str(tmp_path / "o2"),
                "--root-prefix",
                "root",
                "--record",
                str(rec),
                "--expected-md5",
                md5b,
            ]
        )
        == 4
    )


def test_measure_detects_corrupt_and_dihedral_duplicates(tmp_path: Path) -> None:
    a = tmp_path / "a.jpg"
    a.write_bytes(_jpg(7))
    flipped = tmp_path / "f.png"
    ImageOps.mirror(Image.open(a)).save(flipped)
    rot = tmp_path / "r.png"
    Image.open(a).rotate(90, expand=True).save(rot)
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"\xff\xd8\xffnot really a jpeg")
    ma, mf, mr = measure(a), measure(flipped), measure(rot)
    assert ma["decode_ok"] and ma["width"] == 96
    assert measure(bad)["decode_ok"] is False
    for m in (mf, mr):
        assert min(hamming(m["phash"], v) for v in str(ma["phash_d8"]).split(";")) <= 4
    other = measure(_write(tmp_path / "o.jpg", _jpg(99)))
    assert min(hamming(other["phash"], v) for v in str(ma["phash_d8"]).split(";")) > 4


def _write(p: Path, b: bytes) -> Path:
    p.write_bytes(b)
    return p


def test_near_duplicate_pairs_finds_variants_only() -> None:
    base = [0x0F0F_0F0F_0F0F_0F0F, 0x1234_5678_9ABC_DEF0]
    d8 = [
        [base[0], 0xAAAA],
        [base[0] ^ 0b111, 0xBBBB],
        [base[1], 0xCCCC],
        [0xFFFF_0000_FFFF_0000, base[1] ^ 0b1],
    ]
    pairs = {(i, j) for i, j, _ in near_duplicate_pairs(d8, 4)}
    assert (0, 1) in pairs and (2, 3) in pairs and (0, 2) not in pairs


def test_group_split_keeps_families_together_and_stratifies() -> None:
    labels = ["a"] * 100 + ["b"] * 100
    groups = {i: [i] for i in range(200)}
    fam = {1000: list(range(10, 20))}  # a 10-image family of class a
    for i in range(10, 20):
        groups.pop(i)
    groups.update(fam)
    assign = stratified_group_split(groups, labels, (0.7, 0.15, 0.15), seed=1)
    assert assign == stratified_group_split(groups, labels, (0.7, 0.15, 0.15), seed=1)
    for cls in "ab":
        n = {
            s: sum(
                len(groups[g])
                for g, sp in assign.items()
                if sp == s and labels[groups[g][0]] == cls
            )
            for s in ("train", "val", "test")
        }
        assert 65 <= n["train"] <= 75 and 10 <= n["val"] <= 20 and 10 <= n["test"] <= 20
    assert assign[1000] in ("train", "val", "test")  # whole family in exactly one split


def test_split_build_end_to_end(tmp_path: Path) -> None:
    from agrios_ml.data.splits import build

    cm = {
        "classes": ["healthy", "late_blight"],
        "label_map": {"tomato_healthy": "healthy", "tomato_late_blight": "late_blight"},
        "excluded_labels": {"tomato_black_spot": "x"},
        "internal_sources": ["plantvillage"],
        "external_sources": ["plantdoc"],
    }
    (tmp_path / "cm.json").write_text(json.dumps(cm))
    rows = []
    for i in range(60):
        lab = "tomato_healthy" if i % 2 else "tomato_late_blight"
        h = f"{(i * 0x9E3779B97F4A7C15) & (2**64 - 1):016x}"
        rows.append(
            {
                "image_id": f"id{i}",
                "release_path": f"data/x/{i}.jpg",
                "label": lab,
                "crop": "tomato",
                "source": "plantdoc" if i >= 50 else "plantvillage",
                "decode_ok": "True",
                "sha256": f"s{i}",
                "phash_d8": ";".join([h] * 8),
                "width": "256",
                "height": "256",
            }
        )
    rows[51]["phash_d8"] = rows[1]["phash_d8"]  # external image duplicates an internal one
    rows.append({**rows[0], "image_id": "bs", "label": "tomato_black_spot", "sha256": "z"})
    with (tmp_path / "m.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    s = build(tmp_path / "m.csv", tmp_path / "cm.json", tmp_path / "out", 42, 4)
    assert s["split_totals"]["external_test"] == 9
    assert s["split_totals"]["excluded:external_overlaps_internal"] == 1
    assert s["excluded_pre_split"] == 1
    out = list(csv.DictReader((tmp_path / "out" / "tomato_v1_split.csv").open()))
    fam_splits: dict[str, set[str]] = {}
    for r in out:
        fam_splits.setdefault(r["family_id"], set()).add(r["split"])
    assert all(
        len(v) == 1
        or v <= {"external_test", "excluded:external_overlaps_internal", "train", "val", "test"}
        for v in fam_splits.values()
    )
    internal = [r for r in out if r["split"] in ("train", "val", "test")]
    by_fam: dict[str, set[str]] = {}
    for r in internal:
        by_fam.setdefault(r["family_id"], set()).add(r["split"])
    assert all(len(v) == 1 for v in by_fam.values())  # no family crosses internal splits
