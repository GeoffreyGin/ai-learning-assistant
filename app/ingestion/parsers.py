from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class ParsedSection:
    text: str
    page_number: int | None


SUPPORTED_FILE_TYPES = {".pdf", ".md", ".markdown", ".txt"}


def parse_file(path: Path) -> list[ParsedSection]:
    suffix = path.suffix.casefold()
    if suffix not in SUPPORTED_FILE_TYPES:
        raise ValueError("Unsupported file type. Use PDF, Markdown, or TXT.")
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        sections = [
            ParsedSection(text=(page.extract_text() or "").strip(), page_number=index + 1)
            for index, page in enumerate(reader.pages)
        ]
    else:
        sections = [ParsedSection(text=path.read_text(encoding="utf-8").strip(), page_number=None)]
    non_empty = [section for section in sections if section.text]
    if not non_empty:
        raise ValueError("No readable text was found in this document.")
    return non_empty


def chunk_sections(
    sections: list[ParsedSection], *, max_characters: int = 1_200, overlap: int = 150
) -> list[ParsedSection]:
    chunks: list[ParsedSection] = []
    for section in sections:
        start = 0
        while start < len(section.text):
            end = min(len(section.text), start + max_characters)
            if end < len(section.text):
                boundary = section.text.rfind(" ", start + max_characters // 2, end)
                if boundary > start:
                    end = boundary
            text = section.text[start:end].strip()
            if text:
                chunks.append(ParsedSection(text=text, page_number=section.page_number))
            if end == len(section.text):
                break
            start = max(end - overlap, start + 1)
    return chunks
