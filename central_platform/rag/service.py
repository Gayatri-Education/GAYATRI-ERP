"""Gayatri AI Platform — Plug-and-Play RAG Knowledge Service (Phase 16).

Implements the end-to-end knowledge ingestion & retrieval lifecycle:
upload → parse → clean → chunk → metadata → embed → index → validate → publish → query.

Supports multi-format documents (PDF, DOCX, HTML, Markdown, Text, JSON),
dynamic course scoping, rich metadata tagging, and strict data-only security framing.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from central_platform.db import PlatformDatabase
from central_platform.models.schema import (
    CourseLearningContext,
    CourseVisibility,
    KnowledgeContentType,
    KnowledgeVisibilityScope,
    RAGChunk,
    RAGSource,
    RAGSourceStatus,
    User,
    UserRole,
)
from central_platform.rag.cleaner import DocumentCleaner
from central_platform.rag.parsers import DocumentParserRouter, ParsedSection
from central_platform.rag.security import RAGSecuritySanitizer

logger = logging.getLogger("gayatri.central_platform.rag")


class SmartChunker:
    """Chunks structured parsed sections into optimal retrieval blocks respecting sentence boundaries."""

    def __init__(self, target_chunk_chars: int = 600, overlap_chars: int = 80, min_chunk_chars: int = 50):
        self.target_chunk_chars = target_chunk_chars
        self.overlap_chars = overlap_chars
        self.min_chunk_chars = min_chunk_chars

    def chunk_section(
        self,
        section: ParsedSection,
        source_id: str,
        course_id: str,
        subject: str,
        course_version_id: Optional[str] = None,
        visibility_scope: str = "course",
        class_id: Optional[str] = None,
        section_index: int = 0,
    ) -> List[RAGChunk]:
        text = section.text.strip()
        if not text or len(text) < self.min_chunk_chars:
            if not text:
                return []
            # Keep small chunk if meaningful
            return [self._build_chunk(text, section, source_id, course_id, subject, index=0, course_version_id=course_version_id, visibility_scope=visibility_scope, class_id=class_id, section_index=section_index)]

        # If text is already within reasonable bounds
        if len(text) <= self.target_chunk_chars + self.overlap_chars:
            return [self._build_chunk(text, section, source_id, course_id, subject, index=0, course_version_id=course_version_id, visibility_scope=visibility_scope, class_id=class_id, section_index=section_index)]

        # Split text into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks: List[RAGChunk] = []
        current_sentences: List[str] = []
        current_len = 0
        idx = 0

        for sentence in sentences:
            s_len = len(sentence)
            if current_len + s_len > self.target_chunk_chars and current_sentences:
                chunk_text = " ".join(current_sentences)
                chunks.append(self._build_chunk(chunk_text, section, source_id, course_id, subject, index=idx, course_version_id=course_version_id, visibility_scope=visibility_scope, class_id=class_id, section_index=section_index))
                idx += 1
                # Sliding window overlap
                overlap_text: List[str] = []
                overlap_len = 0
                for s in reversed(current_sentences):
                    if overlap_len + len(s) <= self.overlap_chars:
                        overlap_text.insert(0, s)
                        overlap_len += len(s)
                    else:
                        break
                current_sentences = overlap_text
                current_len = overlap_len

            current_sentences.append(sentence)
            current_len += s_len

        if current_sentences:
            chunk_text = " ".join(current_sentences)
            if len(chunk_text) >= self.min_chunk_chars:
                chunks.append(self._build_chunk(chunk_text, section, source_id, course_id, subject, index=idx, course_version_id=course_version_id, visibility_scope=visibility_scope, class_id=class_id, section_index=section_index))

        return chunks

    def _build_chunk(
        self,
        raw_text: str,
        section: ParsedSection,
        source_id: str,
        course_id: str,
        subject: str,
        index: int,
        course_version_id: Optional[str] = None,
        visibility_scope: str = "course",
        class_id: Optional[str] = None,
        section_index: int = 0,
    ) -> RAGChunk:
        clean = DocumentCleaner.clean(raw_text)
        sanitized, _ = RAGSecuritySanitizer.sanitize_document_text(clean)

        text_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:8]
        raw_id = f"{source_id}:{section.chapter}:{section.topic}:{section.page}:{section_index}:{index}:{text_hash}"
        chunk_id = f"chk_{hashlib.sha256(raw_id.encode('utf-8')).hexdigest()[:12]}"

        # Deterministic simple embedding representation (term frequency dictionary / vector)
        words = re.findall(r"\w+", sanitized.lower())
        word_freq: Dict[str, float] = {}
        for w in words:
            word_freq[w] = word_freq.get(w, 0.0) + 1.0

        vis_val = visibility_scope.value if isinstance(visibility_scope, Enum) else str(visibility_scope or "course")
        return RAGChunk(
            id=chunk_id,
            source_id=source_id,
            course_id=course_id,
            subject=subject,
            chapter=section.chapter or "General",
            topic=section.topic or "General",
            concept=section.concept or "",
            difficulty=0.5,
            page=section.page,
            section=section.section_number,
            content_type=section.content_type,
            text=raw_text,
            clean_text=sanitized,
            embedding_vector=[],  # Can store sparse or dense float vectors
            provenance_type=section.raw_metadata.get("authority", "NCERT"),
            metadata_json={
                "title": section.title,
                "term_freq": word_freq,
                "raw_metadata": section.raw_metadata,
            },
            course_version_id=course_version_id,
            visibility_scope=vis_val,
            class_id=class_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )



class RAGService:
    """Authoritative service for plug-and-play RAG knowledge operations."""

    def __init__(self, db: Optional[PlatformDatabase] = None):
        self.db = db or PlatformDatabase()
        self.chunker = SmartChunker()

    def register_source(
        self,
        organization_id: str,
        course_id: str,
        subject: str,
        title: str,
        source_type: str = "text",
        authority: str = "NCERT",
        version: str = "1.0.0",
        content_type: str | KnowledgeContentType = KnowledgeContentType.TEXTBOOK,
        uploaded_by: Optional[str] = None,
        course_version_id: Optional[str] = None,
        visibility_scope: str | KnowledgeVisibilityScope = KnowledgeVisibilityScope.COURSE,
        class_id: Optional[str] = None,
        target_student_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source_id: Optional[str] = None,
    ) -> RAGSource:
        """Register a new knowledge source in draft state."""
        sid = source_id or f"src_{hashlib.sha256(f'{course_id}:{title}:{version}'.encode()).hexdigest()[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        ct_val = content_type.value if isinstance(content_type, KnowledgeContentType) else str(content_type or "textbook")
        vis_val = visibility_scope.value if isinstance(visibility_scope, KnowledgeVisibilityScope) else str(visibility_scope or "course").lower()
        source = RAGSource(
            id=sid,
            organization_id=organization_id,
            course_id=course_id,
            subject=subject,
            title=title,
            source_type=source_type,
            authority=authority,
            version=version,
            status=RAGSourceStatus.DRAFT.value,
            checksum="",
            metadata_json=metadata or {},
            chunk_count=0,
            content_type=ct_val,
            uploaded_by=uploaded_by,
            course_version_id=course_version_id,
            visibility_scope=vis_val,
            class_id=class_id,
            target_student_ids=target_student_ids or [],
            created_at=now,
            updated_at=now,
        )
        return self.db.create_rag_source(source)

    def ingest_document(
        self,
        source_id: str,
        content: str | bytes,
        file_name: str = "",
        override_source_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute full ingestion pipeline: parse -> clean -> chunk -> index -> store."""
        source = self.db.get_rag_source(source_id)
        if not source:
            raise ValueError(f"Knowledge source '{source_id}' not found.")

        # Compute content checksum
        raw_bytes = content.encode("utf-8") if isinstance(content, str) else content
        checksum = hashlib.sha256(raw_bytes).hexdigest()

        if file_name:
            if ".." in file_name or "/" in file_name or "\\" in file_name:
                raise ValueError(f"Path traversal detected in upload filename '{file_name}'.")
            ext = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
            dangerous_exts = {".exe", ".bat", ".cmd", ".sh", ".php", ".py", ".vbs", ".ps1", ".jar", ".dll", ".so"}
            if ext in dangerous_exts:
                raise ValueError(f"Dangerous/executable file extension '{ext}' is prohibited in upload.")

        source_type = override_source_type or source.source_type
        # 1. Parse
        default_meta = {
            "source_id": source.id,
            "course_id": source.course_id,
            "subject": source.subject,
            "authority": source.authority,
            **source.metadata_json,
        }
        parsed_sections = DocumentParserRouter.parse(
            content=content,
            source_type=source_type,
            file_name=file_name,
            default_metadata=default_meta,
        )

        if not parsed_sections:
            raise ValueError("Document parser returned 0 sections. Verify file format and content.")

        # 2. Chunk & Clean
        all_chunks: List[RAGChunk] = []
        for sec_idx, sec in enumerate(parsed_sections):
            chunks = self.chunker.chunk_section(
                sec,
                source.id,
                source.course_id,
                source.subject,
                course_version_id=source.course_version_id,
                visibility_scope=source.visibility_scope,
                class_id=source.class_id,
                section_index=sec_idx,
            )
            all_chunks.extend(chunks)

        if not all_chunks:
            raise ValueError("No valid chunks could be extracted from document.")

        # 3. Store in DB
        self.db.delete_rag_chunks_by_source(source.id)
        added_count = self.db.add_rag_chunks(all_chunks)

        # 4. Update source record
        source.status = RAGSourceStatus.INGESTED.value
        source.checksum = checksum
        source.chunk_count = added_count
        source.updated_at = datetime.now(timezone.utc).isoformat()
        self.db.update_rag_source(source)

        return {
            "source_id": source.id,
            "status": source.status,
            "sections_parsed": len(parsed_sections),
            "chunks_created": added_count,
            "checksum": checksum,
        }

    def ingest_from_provider(
        self, 
        source_id: str, 
        provider: 'central_platform.providers.KnowledgeSource', 
        document_id: str
    ) -> Dict[str, Any]:
        """Ingest knowledge directly from a plugin provider (Phase 10)."""
        content = provider.get_document(document_id)
        if not content:
            raise ValueError(f"Document '{document_id}' not found in provider.")
        return self.ingest_document(source_id, content)

    def validate_source(self, source_id: str) -> Dict[str, Any]:
        """Validate ingested chunks: verify lengths, check concept alignments, detect prompt injections."""
        source = self.db.get_rag_source(source_id)
        if not source:
            raise ValueError(f"Knowledge source '{source_id}' not found.")

        chunks = self.db.get_rag_chunks(source.id, limit=5000)
        if not chunks:
            return {
                "valid": False,
                "errors": ["Source has no ingested chunks."],
                "warnings": [],
                "chunk_count": 0,
            }

        errors: List[str] = []
        warnings: List[str] = []
        total_chars = 0
        concepts_found: Set[str] = set()

        for c in chunks:
            if not c.clean_text.strip():
                errors.append(f"Chunk {c.id} contains empty clean text.")
            if len(c.clean_text) < 10:
                warnings.append(f"Chunk {c.id} is unusually short ({len(c.clean_text)} chars).")
            total_chars += len(c.clean_text)
            if c.concept:
                concepts_found.add(c.concept)

            # Security inspection
            _, warn = RAGSecuritySanitizer.sanitize_document_text(c.text)
            if warn:
                warnings.extend([f"Chunk {c.id}: {w}" for w in warn])

        avg_chunk_size = total_chars / len(chunks) if chunks else 0

        is_valid = len(errors) == 0
        if is_valid:
            source.status = RAGSourceStatus.VALIDATED.value
            self.db.update_rag_source(source)

        return {
            "valid": is_valid,
            "source_id": source.id,
            "status": source.status,
            "chunk_count": len(chunks),
            "average_chunk_chars": round(avg_chunk_size, 1),
            "concepts_covered": list(sorted(concepts_found)),
            "errors": errors,
            "warnings": warnings,
        }

    def upload_knowledge_asset(
        self,
        course_id: str,
        title: str,
        content: str | bytes,
        organization_id: str = "org-default",
        subject: str = "General",
        user: Optional[User] = None,
        user_id: Optional[str] = None,
        user_role: Optional[UserRole | str] = None,
        source_type: str = "text",
        content_type: str | KnowledgeContentType = KnowledgeContentType.TEXTBOOK,
        authority: str = "NCERT",
        version: str = "1.0.0",
        course_version_id: Optional[str] = None,
        visibility_scope: str | KnowledgeVisibilityScope = KnowledgeVisibilityScope.COURSE,
        class_id: Optional[str] = None,
        target_student_ids: Optional[List[str]] = None,
        file_name: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        raise_on_failure: bool = False,
    ) -> RAGSource:
        """Upload and process a knowledge asset through ingestion and validation pipeline.

        Teachers and administrators can upload; students are strictly forbidden (PermissionError).
        Successful processing transitions the asset to READY_FOR_REVIEW.
        Errors transition the asset to FAILED with descriptive error_message.
        """
        role = user.role if user else user_role
        uid = user.id if user else (user_id or "")

        if role is not None:
            r_str = role.value.lower() if hasattr(role, "value") else str(role).lower()
            if r_str in ("student", "userrole.student"):
                raise PermissionError("Students are not permitted to upload knowledge assets.")

        if not course_id or not str(course_id).strip():
            raise ValueError("Knowledge asset requires a non-empty course_id.")
        if not title or not str(title).strip():
            raise ValueError("Knowledge asset requires a non-empty title.")

        if content is None:
            raise ValueError("Content cannot be empty.")
        if isinstance(content, str) and not content.strip():
            raise ValueError("Content cannot be empty.")
        if isinstance(content, bytes) and len(content) == 0:
            raise ValueError("Content cannot be empty.")

        raw_bytes = content.encode("utf-8") if isinstance(content, str) else content
        if len(raw_bytes) > 10 * 1024 * 1024:
            raise ValueError("Content exceeds maximum allowed size of 10MB.")

        if file_name:
            if ".." in file_name or "/" in file_name or "\\" in file_name:
                raise ValueError(f"Path traversal detected in upload filename '{file_name}'.")
            ext = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
            dangerous_exts = {".exe", ".bat", ".cmd", ".sh", ".php", ".py", ".vbs", ".ps1", ".jar", ".dll", ".so"}
            if ext in dangerous_exts:
                raise ValueError(f"Dangerous/executable file extension '{ext}' is prohibited in upload.")

        if course_id:
            c = self.db.get_course(course_id)
            if c and (organization_id == "org-default" or not organization_id):
                organization_id = c.organization_id

        sid = f"src_{hashlib.sha256(f'{course_id}:{title}:{version}'.encode()).hexdigest()[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        ct_val = content_type.value if isinstance(content_type, KnowledgeContentType) else str(content_type or "textbook")
        vis_val = visibility_scope.value if isinstance(visibility_scope, KnowledgeVisibilityScope) else str(visibility_scope or "course").lower()

        source = RAGSource(
            id=sid,
            organization_id=organization_id,
            course_id=course_id,
            subject=subject,
            title=title,
            source_type=source_type,
            authority=authority,
            version=version,
            status=RAGSourceStatus.PROCESSING.value,
            checksum="",
            metadata_json=metadata or {},
            chunk_count=0,
            content_type=ct_val,
            uploaded_by=uid,
            course_version_id=course_version_id,
            visibility_scope=vis_val,
            class_id=class_id,
            target_student_ids=target_student_ids or [],
            created_at=now,
            updated_at=now,
        )
        self.db.create_rag_source(source)

        try:
            checksum = hashlib.sha256(raw_bytes).hexdigest()
            default_meta = {
                "source_id": source.id,
                "course_id": source.course_id,
                "subject": source.subject,
                "authority": source.authority,
                **source.metadata_json,
            }
            parsed_sections = DocumentParserRouter.parse(
                content=content,
                source_type=source_type,
                file_name=file_name,
                default_metadata=default_meta,
            )
            if not parsed_sections:
                raise ValueError("Document parser returned 0 sections. Verify file format and content.")

            all_chunks: List[RAGChunk] = []
            for sec_idx, sec in enumerate(parsed_sections):
                chunks = self.chunker.chunk_section(
                    sec,
                    source.id,
                    source.course_id,
                    source.subject,
                    course_version_id=course_version_id,
                    visibility_scope=vis_val,
                    class_id=class_id,
                    section_index=sec_idx,
                )
                all_chunks.extend(chunks)

            if not all_chunks:
                raise ValueError("No valid chunks could be extracted from document.")

            errors: List[str] = []
            for c in all_chunks:
                if not c.clean_text.strip():
                    errors.append(f"Chunk {c.id} contains empty clean text.")

            if errors:
                raise ValueError("; ".join(errors))

            self.db.delete_rag_chunks_by_source(source.id)
            added_count = self.db.add_rag_chunks(all_chunks)

            source.status = RAGSourceStatus.READY_FOR_REVIEW.value
            source.checksum = checksum
            source.chunk_count = added_count
            source.error_message = None
            source.updated_at = datetime.now(timezone.utc).isoformat()
            return self.db.update_rag_source(source)

        except Exception as exc:
            source.status = RAGSourceStatus.FAILED.value
            source.error_message = str(exc)
            source.updated_at = datetime.now(timezone.utc).isoformat()
            self.db.update_rag_source(source)
            if raise_on_failure:
                raise
            return source

    def approve_knowledge_asset(
        self,
        source_id: str,
        user: Optional[User] = None,
        user_id: Optional[str] = None,
        user_role: Optional[UserRole | str] = None,
    ) -> RAGSource:
        """Approve a processed knowledge asset for publication. Only ORG_ADMIN or SUPER_ADMIN permitted."""
        uid = user.id if user else (user_id or "")
        role = user.role if user else user_role
        r_str = role.value.lower() if hasattr(role, "value") else (str(role).lower() if role else "")

        if r_str not in ("org_admin", "super_admin", "userrole.org_admin", "userrole.super_admin"):
            raise PermissionError("Only institutional administrators (ORG_ADMIN, SUPER_ADMIN) can approve knowledge assets.")

        source = self.db.get_rag_source(source_id)
        if not source:
            raise ValueError(f"Knowledge asset '{source_id}' not found.")

        if source.status == RAGSourceStatus.FAILED.value:
            raise ValueError(f"Cannot approve failed knowledge asset '{source_id}'. Error: {source.error_message}")

        if source.chunk_count == 0:
            raise ValueError(f"Cannot approve empty knowledge asset '{source_id}'. Ingest content first.")

        source.status = RAGSourceStatus.APPROVED.value
        source.updated_at = datetime.now(timezone.utc).isoformat()
        return self.db.update_rag_source(source)

    def publish_knowledge_asset(
        self,
        source_id: str,
        user: Optional[User] = None,
        user_id: Optional[str] = None,
        user_role: Optional[UserRole | str] = None,
    ) -> RAGSource:
        """Publish an approved knowledge asset. Only ORG_ADMIN or SUPER_ADMIN permitted."""
        uid = user.id if user else (user_id or "")
        role = user.role if user else user_role
        r_str = role.value.lower() if hasattr(role, "value") else (str(role).lower() if role else "")

        source = self.db.get_rag_source(source_id)
        if not source:
            raise ValueError(f"Knowledge asset '{source_id}' not found.")

        is_teacher_material = (
            getattr(source, "authority", "") == "TEACHER"
            or getattr(source, "visibility_scope", "") in ("class", "student_targeted")
            or getattr(source, "content_type", "") in ("class_note", "remedial")
        )
        allowed_roles = ("org_admin", "super_admin", "userrole.org_admin", "userrole.super_admin")
        if is_teacher_material:
            allowed_roles = allowed_roles + ("teacher", "userrole.teacher")

        if r_str and r_str not in allowed_roles:
            raise PermissionError("Only institutional administrators (ORG_ADMIN, SUPER_ADMIN) or teachers for class notes can publish knowledge assets.")

        if source.status == RAGSourceStatus.FAILED.value:
            raise ValueError(f"Cannot publish failed knowledge asset '{source_id}'. Error: {source.error_message}")

        if source.chunk_count == 0:
            raise ValueError(f"Cannot publish empty knowledge asset '{source_id}'. Ingest content first.")

        now = datetime.now(timezone.utc).isoformat()
        source.status = RAGSourceStatus.PUBLISHED.value
        source.published_by = uid
        source.published_at = now
        source.updated_at = now
        return self.db.update_rag_source(source)

    def archive_knowledge_asset(
        self,
        source_id: str,
        user: Optional[User] = None,
        user_id: Optional[str] = None,
        user_role: Optional[UserRole | str] = None,
    ) -> RAGSource:
        """Archive a knowledge asset. Admins or the author can archive."""
        source = self.db.get_rag_source(source_id)
        if not source:
            raise ValueError(f"Knowledge asset '{source_id}' not found.")

        if user or user_role:
            uid = user.id if user else (user_id or "")
            role = user.role if user else user_role
            r_str = role.value.lower() if hasattr(role, "value") else (str(role).lower() if role else "")
            if r_str not in ("org_admin", "super_admin", "userrole.org_admin", "userrole.super_admin"):
                if not (uid and source.uploaded_by == uid):
                    raise PermissionError("Only administrators or the asset author can archive knowledge assets.")

        source.status = RAGSourceStatus.ARCHIVED.value
        source.updated_at = datetime.now(timezone.utc).isoformat()
        return self.db.update_rag_source(source)

    def publish_source(
        self,
        source_id: str,
        user: Optional[User] = None,
        user_id: Optional[str] = None,
        user_role: Optional[UserRole | str] = None,
    ) -> RAGSource:
        """Publish a validated knowledge source, making it active for query retrieval."""
        if user or user_role:
            return self.publish_knowledge_asset(source_id, user=user, user_id=user_id, user_role=user_role)

        source = self.db.get_rag_source(source_id)
        if not source:
            raise ValueError(f"Knowledge source '{source_id}' not found.")

        if source.chunk_count == 0:
            raise ValueError(f"Cannot publish empty source '{source_id}'. Ingest content first.")

        now = datetime.now(timezone.utc).isoformat()
        source.status = RAGSourceStatus.PUBLISHED.value
        source.published_at = now
        source.updated_at = now
        return self.db.update_rag_source(source)

    def query(
        self,
        query_text: str,
        course_id: Optional[str] = None,
        subject: Optional[str] = None,
        concept: Optional[str] = None,
        user: Optional[User] = None,
        user_id: Optional[str] = None,
        user_role: Optional[UserRole | str] = None,
        top_k: int = 3,
        confidence_threshold: float = 0.2,
        context: Optional[CourseLearningContext] = None,
        student_id: Optional[str] = None,
        course_version_id: Optional[str] = None,
        class_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute grounded hybrid retrieval scoped to course, version, class, and student.
        Enforces multi-tenant organization isolation and published asset gating.
        """
        sanitized_query = RAGSecuritySanitizer.sanitize_query(query_text)
        if not sanitized_query:
            return {
                "status": "RAG_EMPTY",
                "query": query_text,
                "results": [],
                "count": 0,
                "data_context": "",
            }

        # Resolve effective query scoping parameters
        effective_course_id = course_id
        effective_student_id = student_id or (user.id if user else user_id)
        effective_version_id = course_version_id
        effective_class_id = class_id
        student_org_id = user.organization_id if user else None

        if context:
            if not effective_course_id:
                effective_course_id = context.course_id
            if not effective_student_id:
                effective_student_id = context.student_id
            if not effective_version_id:
                effective_version_id = context.course_version_id
            if not effective_class_id:
                effective_class_id = context.class_id
            if not student_org_id and context.organization_id:
                student_org_id = context.organization_id

        if not student_org_id and effective_student_id:
            usr = self.db.get_user(effective_student_id)
            if usr:
                student_org_id = usr.organization_id

        # Multi-Tenant Org Isolation Check
        if effective_course_id and student_org_id:
            course = self.db.get_course(effective_course_id)
            if course:
                c_vis = course.visibility.value if hasattr(course.visibility, "value") else str(course.visibility).upper()
                if c_vis != "PUBLIC" and course.organization_id != student_org_id:
                    # Check if there is an active course offering for this student's org
                    offering = self.db.get_course_offering_by_org_and_course(student_org_id, effective_course_id)
                    if not offering:
                        return {
                            "status": "RAG_DENIED",
                            "reason": f"Access denied: course '{effective_course_id}' is private to organization '{course.organization_id}' and not offered to organization '{student_org_id}'.",
                            "query": query_text,
                            "results": [],
                            "count": 0,
                            "data_context": "",
                        }

        # Retrieve available chunks from published sources matching course, version, class, student
        chunks: List[RAGChunk] = []
        if effective_course_id:
            chunks = self.db.get_rag_chunks_by_course(
                course_id=effective_course_id,
                subject=subject,
                concept=concept,
                only_published=True,
                course_version_id=effective_version_id,
                class_id=effective_class_id,
                student_id=effective_student_id,
                limit=500,
            )

        # Fallback to general/global published chunks if course has none or no course specified
        if not chunks and not effective_course_id:
            sources = self.db.list_rag_sources(
                course_id=None,
                subject=subject,
                status=RAGSourceStatus.PUBLISHED.value,
                limit=10,
            )
            for s in sources:
                if not s.course_id:
                    chunks.extend(self.db.get_rag_chunks(s.id, limit=100))

        if not chunks:
            if not effective_course_id:
                return self._legacy_fallback_query(sanitized_query, top_k)
            return {
                "status": "RAG_EMPTY",
                "query": query_text,
                "results": [],
                "count": 0,
                "data_context": "",
            }

        # Score chunks using hybrid TF-IDF lexical overlap + concept match + authority weighting
        query_terms = set(re.findall(r"\w+", sanitized_query.lower()))
        scored_results: List[Tuple[float, RAGChunk]] = []

        for chunk in chunks:
            text_lower = chunk.clean_text.lower()
            chunk_terms = set(re.findall(r"\w+", text_lower))
            overlap = query_terms.intersection(chunk_terms)

            lexical_score = 0.0
            if overlap:
                lexical_score = len(overlap) / (math.sqrt(len(query_terms)) * math.sqrt(len(chunk_terms) + 1))

            # Exact phrase bonus
            if sanitized_query.lower() in text_lower:
                lexical_score += 0.35

            # Concept / Chapter / Topic match bonus
            if concept:
                c_lower = concept.lower()
                c_clean = c_lower.replace("cpt-", "").replace("cpt_", "")
                if chunk.concept and (c_lower in chunk.concept.lower() or c_clean in chunk.concept.lower()):
                    lexical_score += 0.25
                elif (chunk.chapter and (c_lower in chunk.chapter.lower() or c_clean in chunk.chapter.lower())) or (chunk.topic and (c_lower in chunk.topic.lower() or c_clean in chunk.topic.lower())):
                    lexical_score += 0.15

            if lexical_score == 0.0:
                continue

            # Authority weight
            authority_multiplier = 1.0
            if chunk.provenance_type == "NCERT":
                authority_multiplier = 1.15
            elif chunk.provenance_type == "APPROVED_CURRICULUM":
                authority_multiplier = 1.10

            final_score = min(1.0, round(lexical_score * authority_multiplier, 3))
            if final_score >= confidence_threshold:
                scored_results.append((final_score, chunk))

        # Sort by score descending
        scored_results.sort(key=lambda x: x[0], reverse=True)
        top_results = scored_results[:top_k]

        if not top_results:
            return {
                "status": "RAG_EMPTY",
                "query": query_text,
                "results": [],
                "count": 0,
                "data_context": "",
            }

        # Format items and build secure data-framed context
        result_items = []
        evidence_cards = []
        for score, chunk in top_results:
            sec_info = f", sec. {chunk.section}" if chunk.section else ""
            cit = f"{chunk.provenance_type}: {chunk.chapter} (p. {chunk.page}{sec_info})"
            item = {
                "chunk_id": chunk.id,
                "source_id": chunk.source_id,
                "chapter": chunk.chapter,
                "topic": chunk.topic,
                "concept": chunk.concept,
                "page": chunk.page,
                "section": chunk.section,
                "content_type": chunk.content_type,
                "text": chunk.clean_text,
                "score": score,
                "citation": cit,
                "provenance_type": chunk.provenance_type,
                "course_version_id": chunk.course_version_id,
                "visibility_scope": chunk.visibility_scope,
                "class_id": chunk.class_id,
            }
            result_items.append(item)
            evidence_cards.append(item)

        data_context = RAGSecuritySanitizer.build_llm_rag_context(evidence_cards)

        return {
            "status": "RAG_OK",
            "query": query_text,
            "results": result_items,
            "count": len(result_items),
            "data_context": data_context,
        }

    def _legacy_fallback_query(self, query_text: str, top_k: int) -> Dict[str, Any]:
        """Fallback to project data/rag JSON files when no published DB sources are present."""
        import json
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent.parent
        rag_dir = project_root / "data" / "rag"
        results = []

        if rag_dir.exists():
            for fpath in rag_dir.glob("ncert_*.json"):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        chunks = data if isinstance(data, list) else (data.get("chunks") or data.get("sections", []))
                        file_chapter = data.get("chapter", "Chemistry") if isinstance(data, dict) else "Chemistry"
                        for c in chunks:
                            text = c.get("text", "")
                            words = [w for w in query_text.lower().split() if len(w) > 2]
                            if any(w in text.lower() for w in words):
                                chk_id = c.get("chunk_id", f"{fpath.stem}_{c.get('page', 100)}")
                                chapter = c.get("chapter", file_chapter)
                                topic = c.get("topic", c.get("subtopic", "General"))
                                page = c.get("page", 100)
                                cit = f"NCERT: {chapter} (p. {page})"
                                results.append(
                                    {
                                        "chunk_id": chk_id,
                                        "source_id": "ncert_textbook",
                                        "chapter": chapter,
                                        "topic": topic,
                                        "concept": "",
                                        "page": page,
                                        "text": text[:300],
                                        "score": 0.88,
                                        "citation": cit,
                                    }
                                )
                                if len(results) >= top_k:
                                    break
                except Exception:
                    continue
                if len(results) >= top_k:
                    break

        if not results:
            return {
                "status": "RAG_EMPTY",
                "query": query_text,
                "results": [],
                "count": 0,
                "data_context": "",
            }

        data_context = RAGSecuritySanitizer.build_llm_rag_context(results)
        return {
            "status": "RAG_OK",
            "query": query_text,
            "results": results,
            "count": len(results),
            "data_context": data_context,
        }

    # ── Backward-Compatibility Aliases ────────────────────────────────────────
    def retrieve(self, **kwargs) -> Dict[str, Any]:
        """Alias for query() - retained for backward compatibility."""
        return self.query(**kwargs)
