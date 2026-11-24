"""Untrusted image intake (SECURITY.md "Input and uploads").

Pipeline: size limit -> content sniffing by Pillow (never filename or client MIME) ->
format allow-list (JPEG, PNG, WebP; single frame) -> dimension and pixel-count limits
BEFORE decoding pixels (decompression bombs) -> full decode -> EXIF orientation applied ->
re-encode to WebP from pixel data only, so EXIF/GPS/XMP/ICC and any trailing payload are
dropped. Originals are not kept (DATA_GOVERNANCE: strip location metadata).
"""

import hashlib
import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG": "jpeg", "PNG": "png", "WEBP": "webp"}


class ImageRejected(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ImageLimits:
    max_bytes: int
    min_side: int
    max_side: int
    max_pixels: int
    store_max_side: int
    thumb_side: int


@dataclass(frozen=True)
class ProcessedImage:
    full: bytes
    thumb: bytes
    width: int
    height: int
    original_format: str
    sha256: str


def _encode(img: Image.Image, max_side: int, quality: int) -> tuple[bytes, int, int]:
    out = img.copy()
    out.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)  # only ever shrinks
    buf = io.BytesIO()
    out.save(buf, format="WEBP", quality=quality, method=4)  # no exif/icc passed
    return buf.getvalue(), out.width, out.height


def process_image(data: bytes, limits: ImageLimits) -> ProcessedImage:
    if not data:
        raise ImageRejected("image_empty", "The file is empty.")
    if len(data) > limits.max_bytes:
        mb = limits.max_bytes // (1024 * 1024)
        raise ImageRejected("image_too_large", f"Each photo must be {mb} MB or smaller.")

    with warnings.catch_warnings():
        # Pillow warns (not errors) between 1x and 2x MAX_IMAGE_PIXELS; treat as an error.
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            img = Image.open(io.BytesIO(data))
            fmt = img.format or ""
            if fmt not in ALLOWED_FORMATS:
                raise ImageRejected(
                    "image_type_not_allowed", "Only JPEG, PNG or WebP photos are accepted."
                )
            if getattr(img, "n_frames", 1) > 1:
                raise ImageRejected("image_animated", "Animated images are not accepted.")
            w, h = img.size  # header only; no pixels decoded yet
            if w * h > limits.max_pixels or max(w, h) > limits.max_side:
                raise ImageRejected(
                    "image_dimensions_too_large", "The photo's dimensions are too large."
                )
            if min(w, h) < limits.min_side:
                raise ImageRejected(
                    "image_too_small",
                    f"The photo is too small. Use at least {limits.min_side} px per side.",
                )
            img.load()  # full decode: truncated/corrupt data fails here
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "L"):
                rgba = img.convert("RGBA")
                bg = Image.new("RGB", rgba.size, (255, 255, 255))
                bg.paste(rgba, mask=rgba.getchannel("A"))
                img = bg
            elif img.mode == "L":
                img = img.convert("RGB")
        except ImageRejected:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ImageRejected(
                "image_dimensions_too_large", "The photo's dimensions are too large."
            ) from exc
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
            raise ImageRejected(
                "image_unreadable", "This file could not be read as a photo."
            ) from exc

    full, fw, fh = _encode(img, limits.store_max_side, quality=90)
    thumb, _, _ = _encode(img, limits.thumb_side, quality=80)
    return ProcessedImage(
        full=full,
        thumb=thumb,
        width=fw,
        height=fh,
        original_format=ALLOWED_FORMATS[fmt],
        sha256=hashlib.sha256(full).hexdigest(),
    )
