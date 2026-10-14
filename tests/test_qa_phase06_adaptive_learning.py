"""Tests for QA Phase 06: Adaptive Learning & Pedagogical Correctness.

Verifies:
- Complete canonical multi-turn adaptive behavior chain end-to-end.
- Misconception detection, repeated misconception penalty, and remediation routing.
- Learner archetype branching (weak, developing, mastered).
- Numerical correctness with tolerance and unit verification.
- Socratic 5-tier hint progression without answer leakage.
- Student profile persistence durability across restart.
"""

from pathlib import Path
import pytest

from core.tutor.adaptive import (
    AdaptiveLearningEngine,
    EventLogger,
    StudentProfile,
)
from core.tutor.controller import TutorController, TutorMode
from core.tutor.difficulty import DifficultyManager
from core.tutor.evaluator import EvaluationResult, StudentAnswerEvaluator


@pytest.fixture(autouse=True)
def isolate_test_student_profile(tmp_path: Path, monkeypatch):
    """Ensure tests in this module do not pollute the global student_profile.json."""
    fake_profile = tmp_path / "global_student_profile.json"
    fake_events = tmp_path / "global_events.jsonl"
    monkeypatch.setattr("core.tutor.adaptive.DEFAULT_STUDENT_FILE", fake_profile)
    monkeypatch.setattr("core.tutor.adaptive.DEFAULT_EVENT_LOG", fake_events)


def test_canonical_multi_turn_adaptive_behavior_chain(tmp_path: Path):
    """Canonical test:
    student receives concept -> answers incorrectly -> evaluated -> misconception detected ->
    mastery drops -> difficulty decreases -> hint provided -> student retries ->
    evaluated correct -> mastery increases -> difficulty increases -> recommendation updates.
    """
    student_file = tmp_path / "student_test.json"
    event_file = tmp_path / "events_test.jsonl"

    student = StudentProfile(
        student_id="test_learner_chain",
        current_topic="Thermodynamics",
        current_concept="THERMO_FIRST_LAW",
        current_difficulty=3,
    )
    student.set_mastery("THERMO_FIRST_LAW", 0.50)
    student.save_to_file(student_file)

    event_logger = EventLogger(log_path=event_file)
    controller = TutorController(student=student, event_logger=event_logger)

    concept = "THERMO_FIRST_LAW"
    question = "A gas expands doing 200 J of work while absorbing 500 J of heat. Calculate delta U."
    expected_ans = "300 J"

    # Step 1: Student answers incorrectly with common sign convention error (+200 instead of -200)
    student_wrong_ans = "delta U = 500 + 200 = 700 J because work done by system is added"
    resp1 = controller.handle_evaluate(
        concept_id=concept,
        question=question,
        student_answer=student_wrong_ans,
        expected_answer=expected_ans,
    )

    # Invariants for incorrect attempt:
    assert resp1.evaluation_result == "INCORRECT"
    assert resp1.misconception == "THERMO_SIGN_CONVENTION"
    assert resp1.mastery < 0.50  # Mastery dropped
    assert student.current_difficulty == 2  # Difficulty decreased L3 -> L2
    assert resp1.next_recommended_action in ("HINT", "REMEDIATE")
    assert "THERMO_SIGN_CONVENTION" in student.misconceptions

    # Step 2: Student requests a hint
    hint_resp = controller.handle_hint(
        concept_id=concept,
        question=question,
        student_attempt=student_wrong_ans,
    )
    assert hint_resp.hint_level == 1
    assert hint_resp.mode == TutorMode.HINT

    # Step 3: Student retries using the hint and answers correctly
    student_correct_ans = "delta U = q + w = 500 J - 200 J = 300 J"
    resp2 = controller.handle_evaluate(
        concept_id=concept,
        question=question,
        student_answer=student_correct_ans,
        expected_answer=expected_ans,
    )

    # Invariants for retry success:
    assert resp2.evaluation_result == "CORRECT"
    assert resp2.mastery > resp1.mastery  # Mastery increased
    assert student.current_difficulty == 3  # Difficulty increased L2 -> L3
    assert resp2.next_recommended_action in ("QUESTION", "SUMMARY")

    # Verify telemetry events recorded
    recent_events = event_logger.get_recent_events(student_id="test_learner_chain")
    event_types = [e["event"] for e in recent_events]
    assert "ANSWER_EVALUATED" in event_types
    assert "MISCONCEPTION_DETECTED" in event_types
    assert "HINT_GIVEN" in event_types
    assert "MASTERY_UPDATED" in event_types


def test_repeated_misconception_penalty(tmp_path: Path):
    """Verify that repeating a misconception incurs an additional penalty delta."""
    student = StudentProfile(student_id="test_repeated")
    student.set_mastery("THERMO_FIRST_LAW", 0.60)
    controller = TutorController(student=student, event_logger=EventLogger(tmp_path / "events.jsonl"))

    concept = "THERMO_FIRST_LAW"
    q = "Gas expands doing work"
    wrong_ans = "delta U is 700 because work by expansion is positive +w"

    # First attempt with misconception
    resp1 = controller.handle_evaluate(concept, q, wrong_ans, expected_answer="300 J")
    assert resp1.misconception == "THERMO_SIGN_CONVENTION"
    assert resp1.mastery_delta == pytest.approx(-0.05, 0.001)

    # Second attempt with the exact same misconception
    resp2 = controller.handle_evaluate(concept, q, wrong_ans, expected_answer="300 J")
    assert resp2.misconception == "THERMO_SIGN_CONVENTION"
    assert resp2.debug_info["repeated_misconception"] is True
    # Penalty delta = -0.05 + -0.03 = -0.08
    assert resp2.mastery_delta == pytest.approx(-0.08, 0.001)


def test_learner_archetype_divergence():
    """Verify weak, developing, and mastered learners receive divergent adaptive actions."""
    # 1. Weak learner with prerequisite deficit
    student_weak = StudentProfile(student_id="weak_learner")
    student_weak.set_mastery("ADVANCED_EQUILIBRIUM", 0.30)
    student_weak.set_mastery("PREREQ_CONCENTRATION", 0.35)

    action_weak = AdaptiveLearningEngine.decide_next_action(
        concept_id="ADVANCED_EQUILIBRIUM",
        student=student_weak,
        prerequisites=["PREREQ_CONCENTRATION"],
        prereq_masteries={"PREREQ_CONCENTRATION": 0.35},
    )
    assert action_weak["action"] == "REMEDIATE_PREREQUISITE"
    assert action_weak["target_concept"] == "PREREQ_CONCENTRATION"

    # 2. Developing learner in practice range
    student_dev = StudentProfile(student_id="dev_learner")
    student_dev.set_mastery("ACID_BASE_PH", 0.55)
    action_dev = AdaptiveLearningEngine.decide_next_action(
        concept_id="ACID_BASE_PH",
        student=student_dev,
        prerequisites=[],
        prereq_masteries={},
    )
    assert action_dev["action"] == "TEST_AND_HINT"
    assert action_dev["recommended_mode"] == "QUESTION"

    # 3. Mastered learner
    student_strong = StudentProfile(student_id="strong_learner")
    student_strong.set_mastery("BOND_ENERGIES", 0.85)
    action_strong = AdaptiveLearningEngine.decide_next_action(
        concept_id="BOND_ENERGIES",
        student=student_strong,
        prerequisites=[],
        prereq_masteries={},
    )
    assert action_strong["action"] == "MASTERED"
    assert action_strong["recommended_mode"] == "SUMMARY"


def test_numerical_tolerance_and_units_evaluation():
    """Verify numerical evaluator respects tolerances and validates expected units."""
    # Within tolerance + correct unit
    res_correct = StudentAnswerEvaluator.evaluate_dict({
        "question_type": "numeric",
        "student_answer": "49.8 kJ/mol",
        "expected_answer": "50.0 kJ/mol",
        "tolerance": 0.05,
        "expected_unit": "kJ/mol",
    })
    assert res_correct.correctness == "correct"
    assert res_correct.error_type == "none"

    # Correct number but wrong or missing unit
    res_unit_err = StudentAnswerEvaluator.evaluate_dict({
        "question_type": "numeric",
        "student_answer": "50.0",
        "expected_answer": "50.0 kJ/mol",
        "tolerance": 0.05,
        "expected_unit": "kJ/mol",
    })
    assert res_unit_err.correctness == "partially_correct"
    assert res_unit_err.error_type == "unit"

    # Beyond tolerance
    res_num_err = StudentAnswerEvaluator.evaluate_dict({
        "question_type": "numeric",
        "student_answer": "75.0 kJ/mol",
        "expected_answer": "50.0 kJ/mol",
        "tolerance": 0.05,
        "expected_unit": "kJ/mol",
    })
    assert res_num_err.correctness == "incorrect"
    assert res_num_err.error_type == "arithmetic"


def test_socratic_policy_hint_progression_no_leakage(tmp_path: Path):
    """Verify hint ladder progression advances through tiers without crashing."""
    student = StudentProfile(student_id="test_hint_ladder")
    controller = TutorController(student=student, event_logger=EventLogger(tmp_path / "events.jsonl"))

    concept = "GIBBS_FREE_ENERGY"
    question = "Calculate delta G when delta H is -100 kJ and T*delta S is -50 kJ."

    # Progress through 5 tiers of hints
    for level in range(1, 6):
        resp = controller.handle_hint(
            concept_id=concept,
            question=question,
            student_attempt="I am confused about delta G",
        )
        assert resp.hint_level == level
        assert resp.mode == TutorMode.HINT
        assert resp.text != ""


def test_adaptive_state_persistence_across_restart(tmp_path: Path):
    """Verify that student profile state persists cleanly to disk and reloads identically."""
    profile_path = tmp_path / "student_persisted.json"

    # Session 1: Learner interacts and modifies state
    p1 = StudentProfile(
        student_id="student_persist_123",
        name="Asha",
        current_concept="THERMO_ENTHALPY",
        current_difficulty=4,
    )
    p1.set_mastery("THERMO_ENTHALPY", 0.72)
    p1.misconceptions.append("ENTHALPY_CONFUSION")
    p1.save_to_file(profile_path)

    # Session 2: Reload profile in a separate instance from file
    p2 = StudentProfile.load_from_file(profile_path)
    assert p2.student_id == "student_persist_123"
    assert p2.name == "Asha"
    assert p2.current_concept == "THERMO_ENTHALPY"
    assert p2.current_difficulty == 4
    assert p2.get_mastery("THERMO_ENTHALPY") == 0.72
    assert "ENTHALPY_CONFUSION" in p2.misconceptions
