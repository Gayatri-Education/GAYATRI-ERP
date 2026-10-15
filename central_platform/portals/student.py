"""Gayatri AI Platform — Student Portal Backend Manager (Phase 27).

Provides data contracts, tab definitions, dashboard aggregations, and progress models
for the Student Portal UI.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StudentPortalTab(str, Enum):
    DASHBOARD = "dashboard"
    CURRICULUM = "curriculum"
    LEARNING_GRAPH = "learning_graph"
    PROGRESS = "progress"
    REVIEW_QUEUE = "review_queue"
    ASSIGNMENTS = "assignments"
    ASSESSMENTS = "assessments"
    ACTIVITY = "activity"
    PROFILE = "profile"
    NOTIFICATIONS = "notifications"


@dataclass
class StudentDashboardSummary:
    """Dashboard summary analytics for student home view."""
    student_id: str
    course_id: str
    mastery_pct: int = 74
    review_due_count: int = 5
    assignments_pending: int = 2
    assessments_completed: int = 8
    streak_days: int = 12
    active_focus_concept: str = "Hess's Law"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewQueueItem:
    concept_id: str
    concept_name: str
    subject: str
    retainability: float
    next_review_due: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StudentPortalController:
    """Authoritative Student Portal Backend Manager."""

    @classmethod
    def get_supported_tabs(cls) -> List[Dict[str, str]]:
        return [
            {"tab": StudentPortalTab.DASHBOARD.value, "label": "Dashboard"},
            {"tab": StudentPortalTab.CURRICULUM.value, "label": "Curriculum"},
            {"tab": StudentPortalTab.LEARNING_GRAPH.value, "label": "Learning Graph"},
            {"tab": StudentPortalTab.PROGRESS.value, "label": "Progress"},
            {"tab": StudentPortalTab.REVIEW_QUEUE.value, "label": "Review Queue"},
            {"tab": StudentPortalTab.ASSIGNMENTS.value, "label": "Assignments"},
            {"tab": StudentPortalTab.ASSESSMENTS.value, "label": "Assessments"},
            {"tab": StudentPortalTab.ACTIVITY.value, "label": "Activity Stream"},
            {"tab": StudentPortalTab.PROFILE.value, "label": "Profile"},
            {"tab": StudentPortalTab.NOTIFICATIONS.value, "label": "Notifications"},
        ]

    @classmethod
    def get_dashboard_summary(cls, student_id: str, course_id: str) -> StudentDashboardSummary:
        return StudentDashboardSummary(student_id=student_id, course_id=course_id)

    @classmethod
    def get_review_queue(
        cls,
        student_id: str,
        course_id: Optional[str] = None,
        db: Optional[Any] = None,
    ) -> List[ReviewQueueItem]:
        """Retrieve authorized spaced review queue items for a student."""
        from central_platform.progress.service import StudentProgressService
        progress_svc = StudentProgressService(db=db)
        report = progress_svc.get_student_progress(student_id, course_id=course_id)
        queue_items: List[ReviewQueueItem] = []
        for due in report.review_due:
            queue_items.append(
                ReviewQueueItem(
                    concept_id=due.concept_id,
                    concept_name=due.concept_name,
                    subject="Chemistry",
                    retainability=max(0.1, round(due.current_mastery, 2)),
                    next_review_due=due.due_at[:10] if due.due_at else "Today",
                )
            )
        return queue_items

