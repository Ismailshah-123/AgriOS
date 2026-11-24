"""Test image factories (generated in memory; no binary fixtures in the repo)."""

import io
import struct
import zlib

from PIL import Image


def make_image(
    fmt: str = "JPEG",
    size: tuple[int, int] = (400, 300),
    *,
    gps: bool = False,
    orientation: int | None = None,
    mode: str = "RGB",
) -> bytes:
    img = Image.new(mode, size, (40, 140, 60) if mode == "RGB" else None)
    buf = io.BytesIO()
    kwargs: dict = {}
    if gps or orientation:
        exif = Image.Exif()
        if gps:
            exif[0x8825] = {1: "N", 2: (31.0, 30.0, 0.0), 3: "E", 4: (74.0, 20.0, 0.0)}
            exif[0x010F] = "SecretPhoneMaker"
        if orientation:
            exif[0x0112] = orientation
        kwargs["exif"] = exif
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


def png_bomb(width: int = 30000, height: int = 30000) -> bytes:
    """A tiny PNG whose header claims a huge canvas (classic decompression bomb)."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00" * 100)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def animated_webp() -> bytes:
    frames = [Image.new("RGB", (300, 300), c) for c in ((255, 0, 0), (0, 255, 0))]
    buf = io.BytesIO()
    frames[0].save(buf, format="WEBP", save_all=True, append_images=frames[1:])
    return buf.getvalue()
