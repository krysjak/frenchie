from __future__ import annotations

import base64
import struct
from pathlib import Path
from typing import Any


MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def detect_media_type(path: Path, data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return MEDIA_TYPES.get(path.suffix.lower())


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        width, height = struct.unpack(">II", data[16:24])
        return width, height
    return None


def _gif_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) >= 10 and data.startswith((b"GIF87a", b"GIF89a")):
        width, height = struct.unpack("<HH", data[6:10])
        return width, height
    return None


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if not data.startswith(b"\xff\xd8"):
        return None
    index = 2
    sof_markers = set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0))
    while index + 3 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9, 0x01} or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            break
        segment_length = struct.unpack(">H", data[index : index + 2])[0]
        if segment_length < 2 or index + segment_length > len(data):
            break
        if marker in sof_markers and segment_length >= 7:
            height, width = struct.unpack(">HH", data[index + 3 : index + 7])
            return width, height
        index += segment_length
    return None


def _webp_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 30 or not (data.startswith(b"RIFF") and data[8:12] == b"WEBP"):
        return None
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    if chunk == b"VP8L" and len(data) >= 25:
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    if chunk == b"VP8 " and len(data) >= 30:
        width = struct.unpack("<H", data[26:28])[0] & 0x3FFF
        height = struct.unpack("<H", data[28:30])[0] & 0x3FFF
        return width, height
    return None


def image_dimensions(media_type: str, data: bytes) -> tuple[int, int] | None:
    if media_type == "image/png":
        return _png_dimensions(data)
    if media_type == "image/jpeg":
        return _jpeg_dimensions(data)
    if media_type == "image/gif":
        return _gif_dimensions(data)
    if media_type == "image/webp":
        return _webp_dimensions(data)
    return None


def build_image_read_result(path: Path, data: bytes) -> dict[str, Any]:
    media_type = detect_media_type(path, data)
    if not media_type:
        raise ValueError(f"Unsupported image format: {path.suffix}")
    dimensions = image_dimensions(media_type, data)
    metadata = {
        "file_path": str(path),
        "media_type": media_type,
        "bytes": len(data),
        "width": dimensions[0] if dimensions else None,
        "height": dimensions[1] if dimensions else None,
    }
    metadata_text = "\n".join(f"{key}: {value}" for key, value in metadata.items() if value is not None)
    encoded = base64.b64encode(data).decode("ascii")
    return {
        **metadata,
        "content": metadata_text,
        "_tool_result_content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": encoded}},
            {"type": "text", "text": metadata_text},
        ],
    }
