"""Untrusted image intake: allow-list by content, size/pixel limits, metadata stripping."""

import io
import uuid
from pathlib import Path

import pytest
from PIL import Image

from app.crop_health.images import ImageLimits, ImageRejected, process_image
from app.storage import signing
from app.storage.base import InvalidKeyError, check_key
from app.storage.local import LocalFileStorage
from tests.images import animated_webp, make_image, png_bomb

LIMITS = ImageLimits(
    max_bytes=2 * 1024 * 1024,
    min_side=128,
    max_side=8000,
    max_pixels=40_000_000,
    store_max_side=2048,
    thumb_side=480,
)


def rejected(data: bytes) -> str:
    with pytest.raises(ImageRejected) as exc:
        process_image(data, LIMITS)
    return exc.value.code


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_allowed_formats_are_reencoded_to_webp(fmt: str) -> None:
    out = process_image(make_image(fmt), LIMITS)
    assert Image.open(io.BytesIO(out.full)).format == "WEBP"
    assert (out.width, out.height, out.original_format) == (400, 300, fmt.lower())
    assert Image.open(io.BytesIO(out.thumb)).size[0] <= 480


def test_gps_and_camera_exif_are_removed() -> None:
    src = make_image("JPEG", gps=True)
    assert b"SecretPhoneMaker" in src  # precondition: metadata really is in the upload
    out = process_image(src, LIMITS)
    for blob in (out.full, out.thumb):
        assert b"SecretPhoneMaker" not in blob
        assert not Image.open(io.BytesIO(blob)).getexif()


def test_exif_orientation_is_applied_before_stripping() -> None:
    out = process_image(make_image("JPEG", (400, 300), orientation=6), LIMITS)
    assert (out.width, out.height) == (300, 400)


def test_large_photo_is_downscaled_for_storage() -> None:
    out = process_image(make_image("PNG", (3000, 1500)), LIMITS)
    assert (out.width, out.height) == (2048, 1024)


def test_transparent_png_is_flattened() -> None:
    out = process_image(make_image("PNG", (300, 300), mode="RGBA"), LIMITS)
    assert Image.open(io.BytesIO(out.full)).mode == "RGB"


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b"", "image_empty"),
        (b"<html><script>alert(1)</script></html>", "image_unreadable"),
        (b"%PDF-1.4 not an image", "image_unreadable"),
        (b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', "image_unreadable"),
        (b"MZ\x90\x00 executable bytes", "image_unreadable"),
    ],
    ids=["empty", "html", "pdf", "svg", "exe"],
)
def test_non_images_are_rejected_regardless_of_name(data: bytes, code: str) -> None:
    assert rejected(data) == code


def test_gif_and_bmp_are_not_allowed() -> None:
    assert rejected(make_image("GIF")) == "image_type_not_allowed"
    assert rejected(make_image("BMP")) == "image_type_not_allowed"


def test_truncated_jpeg_is_rejected() -> None:
    data = make_image("JPEG", (800, 600))
    assert rejected(data[: len(data) // 2]) == "image_unreadable"


def test_decompression_bomb_rejected_before_decoding() -> None:
    bomb = png_bomb()
    assert len(bomb) < 1000
    assert rejected(bomb) == "image_dimensions_too_large"


def test_dimension_limits() -> None:
    assert rejected(make_image("PNG", (100, 400))) == "image_too_small"
    assert rejected(png_bomb(9000, 200)) == "image_dimensions_too_large"


def test_animated_images_rejected() -> None:
    assert rejected(animated_webp()) == "image_animated"


def test_oversized_file_rejected_before_decoding() -> None:
    assert rejected(b"\xff\xd8" + b"0" * (LIMITS.max_bytes + 1)) == "image_too_large"


def test_trailing_payload_after_image_is_not_stored() -> None:
    polyglot = make_image("JPEG") + b"<?php system($_GET['c']); ?>"
    out = process_image(polyglot, LIMITS)
    assert b"<?php" not in out.full


# --------------------------------------------------------------------- storage


@pytest.mark.parametrize(
    "key",
    [
        "../etc/passwd.webp",
        "/abs/x.webp",
        "a/../../b.webp",
        "UPPER.webp",
        "a\\b.webp",
        "x.php",
        "crop-health/a.webp/../../c.webp",
        "",
    ],
)
def test_storage_rejects_unsafe_keys(key: str) -> None:
    with pytest.raises(InvalidKeyError):
        check_key(key)


def test_local_storage_round_trip_and_idempotent_delete(tmp_path: Path) -> None:
    s = LocalFileStorage(tmp_path)
    s.put("crop-health/2026/11/abc-full.webp", b"data", "image/webp")
    assert s.get("crop-health/2026/11/abc-full.webp") == b"data"
    assert [o.key for o in s.list("crop-health")] == ["crop-health/2026/11/abc-full.webp"]
    s.delete("crop-health/2026/11/abc-full.webp")
    s.delete("crop-health/2026/11/abc-full.webp")
    assert s.list("crop-health") == []


# ---------------------------------------------------------------- signed links


def test_signed_links_bind_image_variant_owner_and_expiry() -> None:
    img, owner, secret = uuid.uuid4(), uuid.uuid4(), "s" * 40
    exp, sig = signing.sign(img, "full", owner, 60, secret, now=1000)
    assert signing.verify(img, "full", owner, exp, sig, secret, now=1030)
    assert not signing.verify(img, "full", owner, exp, sig, secret, now=1061)  # expired
    assert not signing.verify(img, "thumb", owner, exp, sig, secret, now=1030)
    assert not signing.verify(uuid.uuid4(), "full", owner, exp, sig, secret, now=1030)
    assert not signing.verify(img, "full", uuid.uuid4(), exp, sig, secret, now=1030)
    assert not signing.verify(img, "full", owner, exp + 999, sig, secret, now=1030)
    assert not signing.verify(img, "full", owner, exp, sig, "t" * 40, now=1030)
