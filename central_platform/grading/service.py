"""Grading and Report Cards Domain Service."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from central_platform.models.grading import (
    ScaleType,
    ReportCardStatus,
    GradingScale,
    GradingTier,
    StudentTermResult,
    StudentReportCard,
)


class GradingService:
    def __init__(self, db):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_grading_scale(
        self,
        organization_id: str,
        name: str,
        code: str,
        scale_type: ScaleType = ScaleType.NINE_POINT,
        tiers: Optional[List[Dict[str, Any]]] = None,
        is_default: bool = False,
    ) -> GradingScale:
        now = self._now()
        scale_id = f"gsc-{uuid.uuid4().hex[:12]}"
        st_val = scale_type.value if hasattr(scale_type, "value") else str(scale_type)

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO grading_scales (
                    id, organization_id, name, code, scale_type, is_default, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    scale_id,
                    organization_id,
                    name,
                    code,
                    st_val,
                    1 if is_default else 0,
                    now,
                    now,
                ),
            )

            if tiers:
                for t in tiers:
                    tier_id = f"gtr-{uuid.uuid4().hex[:12]}"
                    conn.execute(
                        """
                        INSERT INTO grading_scale_tiers (
                            id, organization_id, scale_id, grade_name, grade_point, min_percentage, max_percentage, description, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            tier_id,
                            organization_id,
                            scale_id,
                            t["grade_name"],
                            float(t.get("grade_point", 0.0)),
                            float(t["min_percentage"]),
                            float(t["max_percentage"]),
                            t.get("description"),
                            now,
                        ),
                    )

        return GradingScale(
            id=scale_id,
            organization_id=organization_id,
            name=name,
            code=code,
            scale_type=ScaleType(st_val) if st_val in ScaleType._value2member_map_ else ScaleType.NINE_POINT,
            is_default=is_default,
            created_at=now,
            updated_at=now,
        )

    def get_grading_scale(self, organization_id: str, scale_id: str) -> Optional[GradingScale]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, name, code, scale_type, is_default, created_at, updated_at
                FROM grading_scales
                WHERE id = ? AND organization_id = ?;
                """,
                (scale_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return GradingScale(
                id=row[0],
                organization_id=row[1],
                name=row[2],
                code=row[3],
                scale_type=ScaleType(row[4]) if row[4] in ScaleType._value2member_map_ else ScaleType.NINE_POINT,
                is_default=bool(row[5]),
                created_at=row[6],
                updated_at=row[7],
            )

    def list_grading_scales(self, organization_id: str) -> List[GradingScale]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, name, code, scale_type, is_default, created_at, updated_at
                FROM grading_scales
                WHERE organization_id = ?
                ORDER BY name;
                """,
                (organization_id,),
            )
            rows = cursor.fetchall()

        return [
            GradingScale(
                id=r[0],
                organization_id=r[1],
                name=r[2],
                code=r[3],
                scale_type=ScaleType(r[4]) if r[4] in ScaleType._value2member_map_ else ScaleType.NINE_POINT,
                is_default=bool(r[5]),
                created_at=r[6],
                updated_at=r[7],
            )
            for r in rows
        ]

    def get_grading_tiers(self, organization_id: str, scale_id: str) -> List[GradingTier]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, scale_id, grade_name, grade_point, min_percentage, max_percentage, description, created_at
                FROM grading_scale_tiers
                WHERE scale_id = ? AND organization_id = ?
                ORDER BY min_percentage DESC;
                """,
                (scale_id, organization_id),
            )
            rows = cursor.fetchall()

        return [
            GradingTier(
                id=r[0],
                organization_id=r[1],
                scale_id=r[2],
                grade_name=r[3],
                grade_point=float(r[4]),
                min_percentage=float(r[5]),
                max_percentage=float(r[6]),
                description=r[7],
                created_at=r[8],
            )
            for r in rows
        ]

    def resolve_grade(self, organization_id: str, scale_id: str, percentage: float) -> Dict[str, Any]:
        tiers = self.get_grading_tiers(organization_id, scale_id)
        if not tiers:
            return {"grade_name": "N/A", "grade_point": 0.0, "description": None}

        # Check descending by min_percentage
        for tier in tiers:
            # Allow tiny floating tolerance for upper bound
            if percentage >= tier.min_percentage and percentage <= (tier.max_percentage + 0.01):
                return {
                    "grade_name": tier.grade_name,
                    "grade_point": tier.grade_point,
                    "description": tier.description,
                }

        # Fallback to lowest tier if percentage below lowest min_percentage
        lowest = tiers[-1]
        return {
            "grade_name": lowest.grade_name,
            "grade_point": lowest.grade_point,
            "description": lowest.description,
        }

    def calculate_term_result(
        self,
        organization_id: str,
        student_id: str,
        academic_year_id: str,
        academic_term_id: Optional[str] = None,
        scale_id: Optional[str] = None,
    ) -> StudentTermResult:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT s.max_marks, m.marks_obtained, m.is_absent, m.is_exempt
                FROM exam_student_marks m
                JOIN exam_schedules s ON m.schedule_id = s.id
                JOIN exam_series es ON s.exam_series_id = es.id
                WHERE m.organization_id = ?
                  AND m.student_id = ?
                  AND es.academic_year_id = ?
            """
            params: List[Any] = [organization_id, student_id, academic_year_id]
            if academic_term_id:
                query += " AND es.academic_term_id = ?"
                params.append(academic_term_id)

            cursor.execute(query, params)
            rows = cursor.fetchall()

        total_max = 0.0
        total_obtained = 0.0

        for r in rows:
            max_m = float(r[0])
            obtained = float(r[1]) if r[1] is not None else 0.0
            is_absent = bool(r[2])
            is_exempt = bool(r[3])

            if not is_exempt:
                total_max += max_m
                if not is_absent:
                    total_obtained += obtained

        percentage = round((total_obtained / total_max * 100.0), 2) if total_max > 0 else 0.0

        final_grade = None
        gpa = None
        if scale_id:
            resolved = self.resolve_grade(organization_id, scale_id, percentage)
            final_grade = resolved["grade_name"]
            gpa = resolved["grade_point"]

        now = self._now()
        result_id = f"str-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO student_term_results (
                    id, organization_id, student_id, academic_year_id, academic_term_id,
                    total_marks_obtained, total_max_marks, percentage, gpa, final_grade, rank, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                ON CONFLICT(student_id, academic_year_id, academic_term_id) DO UPDATE SET
                    total_marks_obtained = excluded.total_marks_obtained,
                    total_max_marks = excluded.total_max_marks,
                    percentage = excluded.percentage,
                    gpa = excluded.gpa,
                    final_grade = excluded.final_grade,
                    updated_at = excluded.updated_at;
                """,
                (
                    result_id,
                    organization_id,
                    student_id,
                    academic_year_id,
                    academic_term_id,
                    total_obtained,
                    total_max,
                    percentage,
                    gpa,
                    final_grade,
                    now,
                    now,
                ),
            )

        return StudentTermResult(
            id=result_id,
            organization_id=organization_id,
            student_id=student_id,
            academic_year_id=academic_year_id,
            academic_term_id=academic_term_id,
            total_marks_obtained=total_obtained,
            total_max_marks=total_max,
            percentage=percentage,
            gpa=gpa,
            final_grade=final_grade,
            rank=None,
            created_at=now,
            updated_at=now,
        )

    def generate_report_card(
        self,
        organization_id: str,
        student_id: str,
        academic_year_id: str,
        academic_term_id: Optional[str] = None,
        general_remarks: Optional[str] = None,
    ) -> StudentReportCard:
        now = self._now()
        report_id = f"rc-{uuid.uuid4().hex[:12]}"
        report_number = f"RC-{uuid.uuid4().hex[:8].upper()}"

        # Generate cryptographic SHA-256 tamper hash
        raw_payload = f"{organization_id}:{student_id}:{academic_year_id}:{academic_term_id}:{report_number}:{general_remarks}:{now}"
        document_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO student_report_cards (
                    id, organization_id, student_id, academic_year_id, academic_term_id,
                    report_number, issue_date, status, general_remarks, document_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?);
                """,
                (
                    report_id,
                    organization_id,
                    student_id,
                    academic_year_id,
                    academic_term_id,
                    report_number,
                    now[:10],
                    general_remarks,
                    document_hash,
                    now,
                    now,
                ),
            )

        return StudentReportCard(
            id=report_id,
            organization_id=organization_id,
            student_id=student_id,
            academic_year_id=academic_year_id,
            academic_term_id=academic_term_id,
            report_number=report_number,
            issue_date=now[:10],
            status=ReportCardStatus.DRAFT,
            general_remarks=general_remarks,
            document_hash=document_hash,
            published_at=None,
            created_at=now,
            updated_at=now,
        )

    def publish_report_card(self, organization_id: str, report_card_id: str) -> StudentReportCard:
        now = self._now()
        with self.db._get_connection() as conn:
            conn.execute(
                """
                UPDATE student_report_cards
                SET status = 'PUBLISHED', published_at = ?, updated_at = ?
                WHERE id = ? AND organization_id = ?;
                """,
                (now, now, report_card_id, organization_id),
            )

        card = self.get_report_card(organization_id, report_card_id)
        if not card:
            raise ValueError(f"Report card {report_card_id} not found in organization {organization_id}")
        return card

    def get_report_card(self, organization_id: str, report_card_id: str) -> Optional[StudentReportCard]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, student_id, academic_year_id, academic_term_id,
                       report_number, issue_date, status, general_remarks, document_hash, published_at, created_at, updated_at
                FROM student_report_cards
                WHERE id = ? AND organization_id = ?;
                """,
                (report_card_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return StudentReportCard(
                id=row[0],
                organization_id=row[1],
                student_id=row[2],
                academic_year_id=row[3],
                academic_term_id=row[4],
                report_number=row[5],
                issue_date=row[6],
                status=ReportCardStatus(row[7]) if row[7] in ReportCardStatus._value2member_map_ else ReportCardStatus.DRAFT,
                general_remarks=row[8],
                document_hash=row[9],
                published_at=row[10],
                created_at=row[11],
                updated_at=row[12],
            )

    def list_report_cards_for_student(self, organization_id: str, student_id: str) -> List[StudentReportCard]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, student_id, academic_year_id, academic_term_id,
                       report_number, issue_date, status, general_remarks, document_hash, published_at, created_at, updated_at
                FROM student_report_cards
                WHERE student_id = ? AND organization_id = ?
                ORDER BY issue_date DESC;
                """,
                (student_id, organization_id),
            )
            rows = cursor.fetchall()

        return [
            StudentReportCard(
                id=r[0],
                organization_id=r[1],
                student_id=r[2],
                academic_year_id=r[3],
                academic_term_id=r[4],
                report_number=r[5],
                issue_date=r[6],
                status=ReportCardStatus(r[7]) if r[7] in ReportCardStatus._value2member_map_ else ReportCardStatus.DRAFT,
                general_remarks=r[8],
                document_hash=r[9],
                published_at=r[10],
                created_at=r[11],
                updated_at=r[12],
            )
            for r in rows
        ]
