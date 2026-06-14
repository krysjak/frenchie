from __future__ import annotations

import base64
import math
import re
from pathlib import Path
from typing import Any


PDF_TARGET_RAW_SIZE = 20 * 1024 * 1024
PDF_MAX_PAGES_PER_READ = 20
PDF_AT_MENTION_INLINE_THRESHOLD = 10


def parse_pdf_page_range(pages: str) -> tuple[int, int | None] | None:
    trimmed = pages.strip()
    if not trimmed:
        return None
    if trimmed.endswith("-"):
        first_text = trimmed[:-1]
        if not first_text.isdigit():
            return None
        first = int(first_text)
        return (first, None) if first >= 1 else None
    if "-" not in trimmed:
        if not trimmed.isdigit():
            return None
        page = int(trimmed)
        return (page, page) if page >= 1 else None
    first_text, last_text = trimmed.split("-", 1)
    if not first_text.isdigit() or not last_text.isdigit():
        return None
    first = int(first_text)
    last = int(last_text)
    if first < 1 or last < first:
        return None
    return first, last


def pdf_page_count(data: bytes) -> int | None:
    # This mirrors the TS fallback posture: best-effort metadata, API enforces the hard limit.
    matches = re.findall(rb"/Type\s*/Page\b", data)
    return len(matches) if matches else None


def _range_size(first: int, last: int | None) -> int:
    if last is None:
        return PDF_MAX_PAGES_PER_READ + 1
    return last - first + 1


def build_pdf_read_result(path: Path, pages: str | None = None) -> dict[str, Any]:
    data = path.read_bytes()
    original_size = len(data)
    if original_size == 0:
        raise ValueError(f"PDF file is empty: {path}")
    if not data.startswith(b"%PDF-"):
        raise ValueError(f"File is not a valid PDF (missing %PDF- header): {path}")
    if original_size > PDF_TARGET_RAW_SIZE:
        raise ValueError(f"PDF file exceeds maximum allowed size of {PDF_TARGET_RAW_SIZE} bytes.")

    parsed_pages: tuple[int, int | None] | None = None
    if pages:
        parsed_pages = parse_pdf_page_range(pages)
        if parsed_pages is None:
            raise ValueError(f'Invalid PDF page range: "{pages}"')
        if _range_size(*parsed_pages) > PDF_MAX_PAGES_PER_READ:
            raise ValueError(
                f'Page range "{pages}" exceeds maximum of {PDF_MAX_PAGES_PER_READ} pages per request. Please use a smaller range.'
            )

    count = pdf_page_count(data)
    page_note = f", pages: {count}" if count is not None else ""
    selected_note = f", selected pages: {pages}" if pages else ""
    metadata_text = f"PDF file read: {path} ({original_size} bytes{page_note}{selected_note})"
    encoded = base64.b64encode(data).decode("ascii")
    document_block: dict[str, Any] = {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf", "data": encoded},
    }
    if pages:
        first, last = parsed_pages or (1, 1)
        document_block["context"] = f"Use page range {first}-{last if last is not None else math.inf} from this PDF."
    return {
        "file_path": str(path),
        "media_type": "application/pdf",
        "bytes": original_size,
        "pages": count,
        "selected_pages": pages,
        "content": metadata_text,
        "_tool_result_content": [document_block, {"type": "text", "text": metadata_text}],
    }
