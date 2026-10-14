"""Gayatri AI Platform — Plug-and-Play Multi-Format Document Parsers (Phase 16).

Supports PDF, DOCX, HTML, Markdown, Plain Text, and Structured JSON.
Extracts structured document sections with hierarchical metadata.
"""
from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("gayatri.rag.parsers")


@dataclass
class ParsedSection:
    """A parsed section from a document with preliminary metadata."""
    title: str = ""
    chapter: str = ""
    topic: str = ""
    subtopic: str = ""
    concept: str = ""
    page: int = 1
    section_number: str = ""
    text: str = ""
    content_type: str = "explanation"  # explanation, definition, formula, example, exercise
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


class BaseParser:
    """Base parser interface for all document formats."""
    def parse_text(self, content: str, default_metadata: Optional[Dict[str, Any]] = None) -> List[ParsedSection]:
        raise NotImplementedError

    def parse_bytes(self, content_bytes: bytes, default_metadata: Optional[Dict[str, Any]] = None) -> List[ParsedSection]:
        return self.parse_text(content_bytes.decode("utf-8", errors="replace"), default_metadata)


class TextParser(BaseParser):
    """Parses plain text documents into paragraph or chapter-based sections."""

    def parse_text(self, content: str, default_metadata: Optional[Dict[str, Any]] = None) -> List[ParsedSection]:
        meta = default_metadata or {}
        default_chapter = meta.get("chapter", "General")
        default_topic = meta.get("topic", "General")
        default_subject = meta.get("subject", "General")

        # Split by double newlines or chapter/section headers
        raw_paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
        sections: List[ParsedSection] = []
        current_chapter = default_chapter
        current_topic = default_topic
        page_num = 1

        for i, para in enumerate(raw_paragraphs):
            lines = [l.strip() for l in para.splitlines() if l.strip()]
            if not lines:
                continue

            # Check lines for chapter or section headers
            first_line = lines[0]
            chap_match = re.match(r"^(?:Chapter|Unit)\s*(\d+)?[:\s\-]+(.+)$", first_line, re.IGNORECASE)
            sec_match = re.match(r"^(?:Section\s*)?(\d+\.\d+)[:\s\-]+(.+)$", first_line, re.IGNORECASE)

            if chap_match and len(lines) == 1:
                current_chapter = chap_match.group(2).strip()
                continue
            elif chap_match and len(lines) > 1:
                current_chapter = chap_match.group(2).strip()
                lines = lines[1:]

            if lines:
                first_line = lines[0]
                sec_match = re.match(r"^(?:Section\s*)?(\d+\.\d+)[:\s\-]+(.+)$", first_line, re.IGNORECASE)
                if sec_match:
                    current_topic = sec_match.group(2).strip()
                    lines = lines[1:]

            body_text = " ".join(lines)
            if not body_text:
                continue

            # Check if page marker exists like "[Page 12]" or "--- Page 12 ---"
            page_match = re.search(r"\[Page\s*(\d+)\]|---\s*Page\s*(\d+)\s*---", body_text, re.IGNORECASE)
            if page_match:
                page_num = int(page_match.group(1) or page_match.group(2))
                body_text = re.sub(r"\[Page\s*(\d+)\]|---\s*Page\s*(\d+)\s*---", "", body_text, flags=re.IGNORECASE).strip()
                if not body_text:
                    continue

            sections.append(
                ParsedSection(
                    title=f"{current_chapter} - {current_topic}",
                    chapter=current_chapter,
                    topic=current_topic,
                    subtopic=meta.get("subtopic", ""),
                    concept=meta.get("concept", ""),
                    page=page_num,
                    text=body_text,
                    content_type="explanation",
                    raw_metadata=meta,
                )
            )


        if not sections and content.strip():
            sections.append(
                ParsedSection(
                    title=default_chapter,
                    chapter=default_chapter,
                    topic=default_topic,
                    page=1,
                    text=content.strip(),
                    raw_metadata=meta,
                )
            )

        return sections


class MarkdownParser(BaseParser):
    """Parses Markdown documents preserving #, ##, ### header hierarchy and code blocks."""

    def parse_text(self, content: str, default_metadata: Optional[Dict[str, Any]] = None) -> List[ParsedSection]:
        meta = default_metadata or {}
        default_chapter = meta.get("chapter", "General")
        default_topic = meta.get("topic", "General")

        sections: List[ParsedSection] = []
        lines = content.splitlines()

        current_h1 = default_chapter
        current_h2 = default_topic
        current_h3 = ""
        current_buffer: List[str] = []
        page_num = 1

        def flush_buffer():
            nonlocal current_buffer
            text = "\n".join(current_buffer).strip()
            if text:
                sections.append(
                    ParsedSection(
                        title=f"{current_h1} > {current_h2}" + (f" > {current_h3}" if current_h3 else ""),
                        chapter=current_h1,
                        topic=current_h2,
                        subtopic=current_h3,
                        concept=meta.get("concept", current_h3 or current_h2),
                        page=page_num,
                        text=text,
                        raw_metadata=meta,
                    )
                )
            current_buffer = []

        for line in lines:
            # Check for page indicator
            page_match = re.match(r"^<!--\s*page\s*(\d+)\s*-->", line.strip(), re.IGNORECASE)
            if page_match:
                flush_buffer()
                page_num = int(page_match.group(1))
                continue

            h1_match = re.match(r"^#\s+(.+)$", line)
            h2_match = re.match(r"^##\s+(.+)$", line)
            h3_match = re.match(r"^###\s+(.+)$", line)

            if h1_match:
                flush_buffer()
                current_h1 = h1_match.group(1).strip()
                current_h2 = "General"
                current_h3 = ""
            elif h2_match:
                flush_buffer()
                current_h2 = h2_match.group(1).strip()
                current_h3 = ""
            elif h3_match:
                flush_buffer()
                current_h3 = h3_match.group(1).strip()
            else:
                current_buffer.append(line)

        flush_buffer()
        return sections


class HTMLParser(BaseParser):
    """Parses HTML documents by stripping scripts/styles and preserving semantic text."""

    def parse_text(self, content: str, default_metadata: Optional[Dict[str, Any]] = None) -> List[ParsedSection]:
        meta = default_metadata or {}
        # Remove script and style tags completely
        clean = re.sub(r"<(script|style|svg|noscript)\b[^>]*>.*?</\1>", "", content, flags=re.DOTALL | re.IGNORECASE)
        # Unescape HTML entities
        clean = html.unescape(clean)

        # Convert headers and paragraphs to markdown-style tags for uniform splitting
        clean = re.sub(r"<h1\b[^>]*>(.*?)</h1>", r"\n# \1\n", clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<h2\b[^>]*>(.*?)</h2>", r"\n## \1\n", clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<h3\b[^>]*>(.*?)</h3>", r"\n### \1\n", clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<p\b[^>]*>(.*?)</p>", r"\n\1\n", clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<br\s*/?>", "\n", clean, flags=re.IGNORECASE)
        # Strip all remaining tags without injecting extraneous spaces
        clean = re.sub(r"<[^>]+>", "", clean)
        # Normalize whitespace
        clean = re.sub(r"[ \t]+", " ", clean)

        # Parse with MarkdownParser
        md_parser = MarkdownParser()
        return md_parser.parse_text(clean, default_metadata)



class StructuredJSONParser(BaseParser):
    """Parses structured JSON documents containing chapters, sections, or chunk arrays."""

    def parse_text(self, content: str, default_metadata: Optional[Dict[str, Any]] = None) -> List[ParsedSection]:
        meta = default_metadata or {}
        try:
            data = json.loads(content)
        except Exception as exc:
            raise ValueError(f"Document parser error: Malformed JSON: {exc}") from exc

        sections: List[ParsedSection] = []

        if isinstance(data, list):
            # Array of chunk / section objects
            for idx, item in enumerate(data):
                if isinstance(item, dict):
                    sections.append(
                        ParsedSection(
                            title=item.get("title", item.get("topic", f"Section {idx+1}")),
                            chapter=item.get("chapter", meta.get("chapter", "General")),
                            topic=item.get("topic", meta.get("topic", "General")),
                            subtopic=item.get("subtopic", ""),
                            concept=item.get("concept", meta.get("concept", "")),
                            page=int(item.get("page", idx + 1)),
                            section_number=str(item.get("section", item.get("section_number", ""))),
                            text=item.get("text", item.get("content", "")).strip(),
                            content_type=item.get("content_type", "explanation"),
                            raw_metadata={**meta, **item},
                        )
                    )
        elif isinstance(data, dict):
            # Hierarchical structure: e.g. { "chapter": "...", "sections": [...] }
            chapter = data.get("chapter", meta.get("chapter", "General"))
            sec_list = data.get("sections", data.get("chunks", data.get("items", [])))
            if isinstance(sec_list, list):
                for idx, sec in enumerate(sec_list):
                    if isinstance(sec, dict):
                        sections.append(
                            ParsedSection(
                                title=sec.get("title", sec.get("topic", f"Section {idx+1}")),
                                chapter=chapter,
                                topic=sec.get("topic", meta.get("topic", "General")),
                                subtopic=sec.get("subtopic", ""),
                                concept=sec.get("concept", meta.get("concept", "")),
                                page=int(sec.get("page", idx + 1)),
                                section_number=str(sec.get("section", "")),
                                text=sec.get("text", sec.get("content", "")).strip(),
                                content_type=sec.get("content_type", "explanation"),
                                raw_metadata={**meta, **sec},
                            )
                        )
            else:
                # Single object
                text = data.get("text", data.get("content", ""))
                if text:
                    sections.append(
                        ParsedSection(
                            title=data.get("title", chapter),
                            chapter=chapter,
                            topic=data.get("topic", "General"),
                            concept=data.get("concept", ""),
                            page=int(data.get("page", 1)),
                            text=text.strip(),
                            raw_metadata={**meta, **data},
                        )
                    )

        return [s for s in sections if s.text]


class PDFParser(BaseParser):
    """Extracts text sections from PDF byte streams or text representations."""

    def parse_bytes(self, content_bytes: bytes, default_metadata: Optional[Dict[str, Any]] = None) -> List[ParsedSection]:
        meta = default_metadata or {}
        # Validate PDF magic header
        if not content_bytes.startswith(b"%PDF") and b"%PDF-" not in content_bytes[:1024]:
            raise ValueError("Invalid PDF document: missing %PDF header.")

        try:
            import io
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(content_bytes))
            sections: List[ParsedSection] = []
            chapter = meta.get("chapter", "General")
            topic = meta.get("topic", "General")
            for page_idx, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    sections.append(
                        ParsedSection(
                            title=f"{chapter} - Page {page_idx + 1}",
                            chapter=chapter,
                            topic=topic,
                            page=page_idx + 1,
                            text=page_text.strip(),
                            raw_metadata=meta,
                        )
                    )
            if sections:
                return sections
        except ValueError:
            raise
        except Exception as exc:
            logger.debug("Primary pypdf extraction failed, falling back to regex: %s", exc)

        # Fallback text stream regex parser for standard PDF text operators
        try:
            raw_str = content_bytes.decode("latin1", errors="ignore")
            # Extract parenthesized strings in text blocks (Tj, TJ)
            matches = re.findall(r"\((.*?)\)\s*T[jJ]", raw_str)
            if matches:
                extracted = " ".join(matches)
                text_parser = TextParser()
                return text_parser.parse_text(extracted, meta)
        except Exception as exc:
            logger.debug("PDF regex stream extraction failed: %s", exc)

        return []


class DocxParser(BaseParser):
    """Extracts text sections from DOCX document packages or XML text streams."""

    def parse_bytes(self, content_bytes: bytes, default_metadata: Optional[Dict[str, Any]] = None) -> List[ParsedSection]:
        meta = default_metadata or {}
        import zipfile
        import io
        import xml.etree.ElementTree as ET

        if not content_bytes.startswith(b"PK\x03\x04"):
            raise ValueError("Invalid DOCX document: missing PK ZIP package header.")

        try:
            with zipfile.ZipFile(io.BytesIO(content_bytes)) as docx_zip:
                if "word/document.xml" not in docx_zip.namelist():
                    raise ValueError("Invalid DOCX document: missing word/document.xml package entry.")
                xml_content = docx_zip.read("word/document.xml")
                tree = ET.fromstring(xml_content)
                # Find all paragraph tags <w:p>
                paragraphs: List[str] = []
                for p in tree.iter():
                    if p.tag.endswith("}p"):
                        # Collect all text in paragraph
                        p_text = "".join(node.text for node in p.iter() if node.tag.endswith("}t") and node.text)
                        if p_text.strip():
                            paragraphs.append(p_text.strip())
                if paragraphs:
                    text = "\n\n".join(paragraphs)
                    return TextParser().parse_text(text, meta)
        except zipfile.BadZipFile as exc:
            raise ValueError(f"Corrupt DOCX package: {exc}") from exc
        except ValueError:
            raise
        except Exception as exc:
            logger.debug("DOCX XML extraction failed: %s", exc)
            raise ValueError(f"Failed to parse DOCX document structure: {exc}") from exc

        return []


class DocumentParserRouter:
    """Dispatches document content to appropriate format parser based on file extension or source type."""

    ALLOWED_EXTENSIONS = {
        "pdf", "docx", "doc", "html", "htm", "md", "markdown", "json", "txt", "text", ""
    }

    @classmethod
    def parse(
        cls,
        content: str | bytes,
        source_type: str = "text",
        file_name: str = "",
        default_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[ParsedSection]:
        meta = default_metadata or {}

        # Resolve source type from filename extension if source_type is generic
        ext = Path(file_name).suffix.lower().lstrip(".") if file_name else ""
        if ext and ext not in cls.ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported document extension: '.{ext}'")

        fmt = source_type.lower()
        if fmt in ["auto", "text", ""]:
            if ext in ["pdf"]:
                fmt = "pdf"
            elif ext in ["docx", "doc"]:
                fmt = "docx"
            elif ext in ["html", "htm"]:
                fmt = "html"
            elif ext in ["md", "markdown"]:
                fmt = "markdown"
            elif ext in ["json"]:
                fmt = "json"
            else:
                fmt = "text"

        if fmt == "pdf":
            parser = PDFParser()
            if isinstance(content, str):
                return parser.parse_bytes(content.encode("utf-8"), meta)
            return parser.parse_bytes(content, meta)

        elif fmt in ["docx", "doc"]:
            parser = DocxParser()
            if isinstance(content, str):
                return parser.parse_bytes(content.encode("utf-8"), meta)
            return parser.parse_bytes(content, meta)

        elif fmt in ["html", "htm"]:
            text = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
            return HTMLParser().parse_text(text, meta)

        elif fmt in ["md", "markdown"]:
            text = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
            return MarkdownParser().parse_text(text, meta)

        elif fmt in ["json", "structured_json"]:
            text = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
            return StructuredJSONParser().parse_text(text, meta)

        else:
            text = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
            return TextParser().parse_text(text, meta)
