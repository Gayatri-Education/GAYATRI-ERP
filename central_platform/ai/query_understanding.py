"""Query Understanding Engine for Phase 16.

Adds structured query interpretation using local SLM / AI Gateway with Pydantic schema
validation and infallible deterministic fallback.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from core.tutor.intents import (
    CHEMISTRY_CONCEPT_PATTERNS,
    CHEMISTRY_SAFETY_PATTERN,
    INTENT_RULES,
    PROMPT_INJECTION_PATTERN,
    QueryIntent,
)

logger = logging.getLogger("gayatri.query_understanding")


class StructuredQueryInterpretation(BaseModel):
    """Authoritative Pydantic contract for structured query interpretation (Phase 16)."""
    intent: str = Field(default="concept_explanation", description="Classified query intent")
    detected_concepts: List[str] = Field(default_factory=list, description="Extracted domain/chemistry concepts")
    domain: str = Field(default="Chemistry", description="Academic domain/subject")
    complexity: str = Field(default="intermediate", description="Query complexity: basic, intermediate, advanced")
    requires_rag: bool = Field(default=True, description="Whether query requires RAG retrieval")
    requires_calculation: bool = Field(default=False, description="Whether query requires numerical calculation")
    requires_code_execution: bool = Field(default=False, description="Whether query requires code/tool execution")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0, description="Interpretation confidence score")
    rewritten_query: Optional[str] = Field(default=None, description="Contextual query rewrite")
    security_flag: Optional[str] = Field(default=None, description="Security/safety flag if violation detected")

    @field_validator("complexity")
    @classmethod
    def validate_complexity(cls, v: str) -> str:
        v_clean = str(v).lower().strip()
        if v_clean in ("basic", "intermediate", "advanced"):
            return v_clean
        return "intermediate"


class QueryUnderstandingEngine:
    """Structured Query Understanding Engine with SLM integration and deterministic fallback."""

    def __init__(self, slm_client: Optional[Any] = None):
        self.slm_client = slm_client

    def fallback_interpret(self, query: str, context_history: Optional[List[str]] = None) -> StructuredQueryInterpretation:
        """Deterministic fallback rule-based query parser (infallible)."""
        clean_query = query.strip()
        
        # 1. Security Check
        if PROMPT_INJECTION_PATTERN.search(clean_query):
            return StructuredQueryInterpretation(
                intent=QueryIntent.PROMPT_INJECTION.value,
                detected_concepts=[],
                complexity="basic",
                requires_rag=False,
                confidence=1.0,
                security_flag="PROMPT_INJECTION",
            )
            
        if CHEMISTRY_SAFETY_PATTERN.search(clean_query):
            return StructuredQueryInterpretation(
                intent=QueryIntent.CHEMISTRY_SAFETY.value,
                detected_concepts=[],
                complexity="advanced",
                requires_rag=False,
                confidence=1.0,
                security_flag="CHEMISTRY_SAFETY",
            )

        # 2. Concept Extraction
        detected = []
        for concept_name, pattern in CHEMISTRY_CONCEPT_PATTERNS:
            if pattern.search(clean_query):
                detected.append(concept_name)

        # 3. Intent Detection
        q_lower = clean_query.lower()
        matched_intent = QueryIntent.CONCEPT_EXPLANATION
        if any(w in q_lower for w in ["hi", "hello", "hey", "greetings"]):
            matched_intent = QueryIntent.GREETING
        elif any(w in q_lower for w in ["define", "what is", "definition"]):
            matched_intent = QueryIntent.DEFINITION
        else:
            for rule_intent, pattern in INTENT_RULES:
                if rule_intent in (QueryIntent.PROMPT_INJECTION, QueryIntent.CHEMISTRY_SAFETY):
                    continue
                if pattern.search(clean_query):
                    matched_intent = rule_intent
                    break

        intent = matched_intent.value
        requires_calc = False
        requires_rag = True
        complexity = "intermediate"

        if matched_intent == QueryIntent.GREETING:
            requires_rag = False
            complexity = "basic"
        elif matched_intent == QueryIntent.DEFINITION:
            complexity = "basic"
        elif matched_intent in (QueryIntent.NUMERICAL, QueryIntent.PROBLEM_SOLVING):
            requires_calc = True
            complexity = "advanced"
        elif matched_intent in (QueryIntent.DERIVATION, QueryIntent.MECHANISM, QueryIntent.EXAM):
            complexity = "advanced"
        elif matched_intent in (QueryIntent.HINT, QueryIntent.CLARIFICATION, QueryIntent.WHY, QueryIntent.COMPARISON):
            complexity = "intermediate"

        # Contextual rewrite if follow-up
        rewritten = None
        if context_history and len(clean_query.split()) <= 4:
            last_context = context_history[-1]
            rewritten = f"{clean_query} (Context: {last_context})"

        return StructuredQueryInterpretation(
            intent=intent,
            detected_concepts=detected,
            domain="Chemistry",
            complexity=complexity,
            requires_rag=requires_rag,
            requires_calculation=requires_calc,
            requires_code_execution=requires_calc,
            confidence=0.85 if detected else 0.70,
            rewritten_query=rewritten,
            security_flag=None,
        )

    def interpret_query(
        self,
        query: str,
        context_history: Optional[List[str]] = None,
        use_slm: bool = True,
    ) -> StructuredQueryInterpretation:
        """Interpret user query using SLM with schema validation, falling back to deterministic parser."""
        if not query or not query.strip():
            return StructuredQueryInterpretation(
                intent="greeting",
                detected_concepts=[],
                confidence=1.0,
            )

        # Attempt SLM structured interpretation if client available
        if use_slm and self.slm_client:
            try:
                slm_prompt = (
                    f"Analyze student query and output JSON matching schema:\n"
                    f"Query: \"{query}\"\n"
                    f"Output JSON with keys: intent, detected_concepts, domain, complexity, "
                    f"requires_rag, requires_calculation, requires_code_execution, confidence"
                )
                raw_response = self.slm_client.generate(slm_prompt)
                
                # Parse JSON
                if isinstance(raw_response, dict):
                    data = raw_response
                else:
                    # Extract JSON substring
                    match = re.search(r"\{.*\}", str(raw_response), re.DOTALL)
                    if not match:
                        raise ValueError("No valid JSON found in SLM response string")
                    data = json.loads(match.group(0))

                # Validate with Pydantic contract
                interpretation = StructuredQueryInterpretation(**data)
                return interpretation
            except Exception as exc:
                logger.warning(f"SLM query interpretation failed or schema validation error ({exc}); using fallback parser.")

        # Infallible Deterministic Fallback
        return self.fallback_interpret(query, context_history)
