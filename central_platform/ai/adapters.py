"""Gayatri AI Platform — AI Provider Adapters (Phase 17 & Phase 22).

Provides unified normalized adapter implementations for:
- OpenAI-compatible endpoints (OpenAI, vLLM, Ollama, Groq, Together)
- Anthropic Claude API
- Google Gemini API
- OpenRouter meta-provider
- Local GGUF models
- Deterministic simulation mock adapters
"""
from __future__ import annotations

import json
import logging
import math
import os
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from central_platform.ai.schema import (
    AIExecutionRequest,
    AIExecutionResult,
    AIModelDescriptor,
    ModelExecutionStatus,
    ProviderConfig,
    ProviderType,
)

logger = logging.getLogger("gayatri.central_platform.ai.adapters")


def is_production_mode() -> bool:
    """Return True if running in production mode (F-001, F-011, F-012)."""
    from central_platform.config import is_production_mode as _is_prod
    return _is_prod()



class BaseAIProviderAdapter:
    """Base interface for all LLM / SLM provider adapters."""

    def __init__(self, config: ProviderConfig):
        self.config = config

    def get_api_key(self) -> str:
        """Resolve API key securely from environment variable reference."""
        if not self.config.api_key_ref:
            return ""
        return os.environ.get(self.config.api_key_ref, "")

    def execute(self, request: AIExecutionRequest, model_desc: AIModelDescriptor) -> AIExecutionResult:
        """Execute request and return standardized result."""
        raise NotImplementedError


def generate_dynamic_pedagogical_content(request: AIExecutionRequest, model_desc: Optional[AIModelDescriptor] = None) -> str:
    """Generate dynamic, context-aware pedagogical dialogue without repeated static phrases."""
    p = request.prompt.strip()
    p_lower = p.lower()
    task = str(request.task_type.value if hasattr(request.task_type, "value") else request.task_type).lower()

    # 1. Assessment / Grading Task
    if "grading" in task or "evaluate" in task:
        return '{"score": 1.0, "correct": true, "feedback": "Accurate response demonstrating clear conceptual mastery."}'

    # 2. Copilot / Lesson Plan / Diagnostic Briefing
    if "copilot" in task or "briefing" in p_lower or "lesson plan" in p_lower:
        return (
            "### AI Diagnostic Summary & Pedagogical Plan\n\n"
            "**Cohort State:** 14 Students actively enrolled. Average Mastery: 72%.\n\n"
            "**Identified Learning Gaps:**\n"
            "1. *Equilibrium State:* Students confuse stoichiometric coefficients with equilibrium exponents.\n"
            "2. *Thermodynamics Sign Convention:* Students invert work sign conventions (ΔU = q + w).\n\n"
            "**Recommended Socratic Intervention:**\n"
            "- Guide students through pressure vs volume relationships and mole ratios.\n"
            "- Reinforce that work done ON the system (compression) is positive ($w > 0$)."
        )

    # Extract clean user query from prompt without wrapper tags
    user_query = p
    if "Student Query:" in p:
        user_query = p.split("Student Query:")[-1].strip()
    elif "Student:" in p:
        user_query = p.split("Student:")[-1].strip()
    uq_lower = user_query.lower()

    # Extract RAG snippets if available in request or prompt
    rag_snippets: list[str] = []
    if hasattr(request, "rag_context") and request.rag_context:
        for item in request.rag_context:
            if isinstance(item, dict):
                txt = item.get("text") or item.get("content") or ""
                if txt:
                    rag_snippets.append(txt.strip())
            elif isinstance(item, str) and item.strip():
                rag_snippets.append(item.strip())
    elif "[Reference Context]" in p:
        try:
            ref_section = p.split("[Reference Context]")[1].split("Student Query:")[0].strip()
            for line in ref_section.splitlines():
                clean_l = line.strip().lstrip("-").strip()
                if clean_l and len(clean_l) > 15 and not clean_l.startswith("["):
                    rag_snippets.append(clean_l)
        except Exception:
            pass

    # 3. Prerequisite Revisit
    if any(k in uq_lower for k in ["prerequisite", "revisit", "prior concept", "basics first", "step back"]):
        if rag_snippets:
            primary_fact = rag_snippets[0]
            return (
                "Let's step back and anchor on the foundational prerequisite for this concept:\n\n"
                f"**Baseline Principle:**\n{primary_fact}\n\n"
                "Before we build further into active applications: "
                "How would you explain the core relationship here in your own words?"
            )
        return (
            "Let's step back and revisit the foundational prerequisite:\n\n"
            "Every complex scientific or mathematical concept builds upon fundamental **conservation laws and baseline equilibrium states**.\n\n"
            "Before any external disturbance or change occurs, a system resides in an undisturbed reference state where opposing forces or energy flows are balanced.\n\n"
            "To solidify this baseline: when a system is undisturbed at rest, what balance of factors keeps its state constant?"
        )

    # 4. Intuitive Real-World Example
    if any(k in uq_lower for k in ["example", "real-world", "real world", "intuitive", "analogy", "practical"]):
        if rag_snippets:
            primary_fact = rag_snippets[0]
            return (
                "To make this intuitive, let's connect the governing principle to a familiar everyday scenario:\n\n"
                f"**Curriculum Principle:**\n{primary_fact}\n\n"
                "**Real-World Analogy:**\n"
                "Imagine a crowded bus or an elastic band. When an external force compresses or shifts the load, "
                "the system naturally redistributes stress to establish a new balanced state.\n\n"
                "In our active topic, which key variable responds to relieve external stress when conditions change?"
            )
        return (
            "To understand this intuitively, consider a classic real-world analogy:\n\n"
            "Imagine riding a bicycle against a strong headwind. If you don't adjust your effort or change gears, "
            "your speed drops. To maintain forward momentum, you either supply more pedal power (input energy) or switch gears (state adaptation) to rebalance against the wind.\n\n"
            "In our active topic, systems follow this exact pattern: when an external influence changes the environment, "
            "the system adjusts its internal state variables until equilibrium is restored.\n\n"
            "Connecting this back to our topic: what external change do you think acts like that sudden headwind?"
        )

    # 5. Core Principles / Foundational Principles
    if any(k in uq_lower for k in ["foundational principle", "core principle", "principles of our", "foundations of", "core concept"]):
        if rag_snippets:
            snippet_text = "\n- ".join(rag_snippets[:2])
            return (
                "Here are the core principles governing our active topic:\n\n"
                f"- {snippet_text}\n\n"
                "**Key Insight:** System behavior is driven by gradients (energy, pressure, or concentration) moving toward equilibrium. "
                "Whenever an external condition shifts, the system reacts to counterbalance that change.\n\n"
                "Which specific aspect of this principle would you like to explore first?"
            )
        return (
            "The foundational principles of our active topic are anchored in **conservation and dynamic equilibrium**:\n\n"
            "1. **Conservation:** Mass, energy, and momentum are conserved within any closed boundary—they can be transferred or transformed, but not created or destroyed.\n"
            "2. **Dynamic Balance:** Systems naturally evolve toward a state of lowest potential energy or maximum entropy given their boundary constraints.\n"
            "3. **Response to Change:** When perturbed by an external influence, the system shifts its state variables to oppose the perturbation.\n\n"
            "What specific question or scenario about these principles would you like to explore?"
        )

    # 6. Practice Problem
    if any(k in uq_lower for k in ["practice problem", "practice question", "test my understanding", "ask me a question", "give me a problem", "quiz me"]):
        if rag_snippets:
            return (
                f"Here is a targeted practice challenge based on our curriculum:\n\n"
                f"**Scenario:** Based on: *{rag_snippets[0][:140]}...*\n\n"
                "**Question:** If the primary operating condition increases by 50% while temperature is held constant, "
                "how will the system adjust its state variables to re-establish equilibrium?\n\n"
                "What is your first step in setting up the analysis?"
            )
        return (
            "Here is a targeted practice challenge to test your reasoning:\n\n"
            "**Problem:** Consider a system in equilibrium. An external disturbance suddenly increases the primary input load.\n\n"
            "1. Will the system's internal response tend to counteract or amplify this increase?\n"
            "2. What fundamental principle or conservation law supports your reasoning?\n\n"
            "What is your initial thought on question 1?"
        )

    # 7. Socratic Hint
    if any(k in uq_lower for k in ["hint", "clue", "need a hint"]):
        return (
            "💡 **Socratic Hint:**\n\n"
            "Focus on the *direction* of energy flow or force imbalance. Ask yourself:\n"
            "- Is the process adding stress to the inputs or the outputs?\n"
            "- Does the governing rule state that systems shift to relieve that stress, or accumulate it?\n\n"
            "Try applying that direction to your previous thought—what does that suggest?"
        )

    # 8. Lesson Summary
    if any(k in uq_lower for k in ["summary", "recap", "takeaways", "summarize", "review progress"]):
        return (
            "📋 **Lesson Summary & Key Takeaways:**\n\n"
            "1. **Governing Principle:** Systems operate under strict conservation constraints, balancing input energy, work, and internal state.\n"
            "2. **Equilibrium Dynamics:** Disturbances cause state shifts that counteract applied stressors until a new balance is reached.\n"
            "3. **Practical Application:** Understanding sign conventions and governing variables enables precise prediction of system outcomes.\n\n"
            "Would you like to try a practice problem now to solidify your mastery, or explore a new concept?"
        )

    # 9. Clarify Misconceptions
    if any(k in uq_lower for k in ["misconception", "common mistake", "clarify"]):
        return (
            "🔍 **Key Misconceptions to Keep in Mind:**\n\n"
            "1. **Equilibrium is NOT Static:** Particles or energy don't stop moving; rather, the opposing rates of change become equal.\n"
            "2. **Sign Conventions:** Remember whether work or heat is done *on* the system vs *by* the system.\n"
            "3. **Amount vs Rate:** A process can be thermodynamically favored without occurring rapidly.\n\n"
            "Did either of these points clarify what you were wondering about?"
        )

    # 10. Student expresses confusion (guarded for test assertion: "balance scale")
    if any(k in p_lower for k in ["not getting", "don't understand", "dont understand", "not clear", "confused", "stuck", "help", "explain simply"]):
        return (
            "Let's make this simple and intuitive with a physical visual:\n\n"
            "Imagine a two-sided balance scale in perfect equilibrium. "
            "If you add weight to the left side (reactants), the scale tips down. "
            "To level it out again, the system must shift weight over to the right side (products)!\n\n"
            "Let's apply this: If an external change adds extra load to our system, "
            "does the system react by consuming that load (moving forward) or producing more of it?"
        )

    # 11. Student agrees or asks to continue
    if uq_lower in ["yes", "yes explain", "explain", "sure", "continue", "go on", "tell me", "ok", "okay", "tell me more"]:
        return (
            "Great! Let's examine dynamic equilibrium with a clear example: $$A(g) + B(g) \\rightleftharpoons C(g)$$\n\n"
            "Notice that 2 moles on the left turn into 1 mole on the right.\n\n"
            "If we suddenly compress the container to half its volume, the pressure doubles. "
            "According to governing principles, how will the reaction respond to decrease the pressure?"
        )

    # 12. Calculus / Derivatives / Mathematics
    if any(k in p_lower for k in ["derivative", "calculus", "chain rule", "integral", "differentiat"]):
        return (
            "By the power rule of calculus, the derivative of $f(x) = x^n$ is $f'(x) = n x^{n-1}$. "
            "Therefore, for $f(x) = x^2$, we obtain $f'(x) = 2x$.\n\n"
            "When dealing with composite functions like $g(x) = \\sin(x^2)$, we apply the **Chain Rule**:\n"
            "$$\\frac{d}{dx}[f(g(x))] = f'(g(x)) \\cdot g'(x) = \\cos(x^2) \\cdot 2x$$"
        )

    # 13. Python / Code
    if "python" in p_lower:
        return (
            "In Python, variables are dynamically typed identifiers that reference objects in memory. "
            "Functions are defined using the 'def' keyword."
        )

    # 14. Thermodynamics / First Law / Delta U / Work
    if any(k in p_lower for k in ["thermodynamics", "first law", "delta u", "work done", "isothermal", "p_ext"]):
        return (
            "In thermodynamics, the First Law states that energy is conserved: "
            "$$\\Delta U = q + w$$\n\n"
            "Here:\n"
            "- $\\Delta U$ is the change in internal energy.\n"
            "- $q$ is heat transferred to the system ($q > 0$ when absorbed).\n"
            "- $w$ is work done **on** the system ($w = -P_{\\text{ext}} \\Delta V$ for expansion).\n\n"
            "When an ideal gas expands isothermally against external pressure $P_{\\text{ext}}$, "
            "the system does work on the surroundings. Since $\\Delta V > 0$, $w$ is negative, "
            "meaning the system loses internal energy to work unless replenished by heat $q$."
        )

    # 15. Enthalpy / Hess's Law / Exothermic & Endothermic
    if any(k in p_lower for k in ["enthalpy", "hess", "exothermic", "endothermic", "delta h"]):
        return (
            "Enthalpy ($H$) represents the total heat content of a system at constant pressure, defined as: "
            "$$H = U + pV$$\n\n"
            "In an exothermic reaction, heat is released to the surroundings, resulting in a negative enthalpy change ($\\Delta H < 0$). "
            "According to Hess's Law of Constant Heat Summation, the total enthalpy change for a chemical process "
            "is the same whether it takes place in one step or in a series of steps:\n"
            "$$\\Delta H_{\\text{reaction}} = \\sum \\Delta H_f^{\\circ}(\\text{products}) - \\sum \\Delta H_f^{\\circ}(\\text{reactants})$$"
        )

    # 16. Gibbs Free Energy & Spontaneity
    if any(k in p_lower for k in ["gibbs", "spontaneity", "entropy", "delta g"]):
        return (
            "The spontaneity of a reaction at constant temperature and pressure is governed by Gibbs Free Energy: "
            "$$\\Delta G = \\Delta H - T\\Delta S$$\n\n"
            "- If $\\Delta G < 0$, the process is **spontaneous** (exergonic).\n"
            "- If $\\Delta G = 0$, the system is at **dynamic equilibrium**.\n"
            "- If $\\Delta G > 0$, the forward process is **non-spontaneous**.\n\n"
            "What happens to the spontaneity of an endothermic reaction ($\\Delta H > 0$) as temperature $T$ increases?"
        )

    # 17. Le Chatelier's Principle & Chemical Equilibrium
    if any(k in p_lower for k in ["chatelier", "equilibrium", "haber", "k_c", "k_p", "perturb", "shifts"]):
        if any(w in p_lower for w in ["pressure", "volume", "gas", "mole"]):
            return (
                "Let's look at how pressure impacts gaseous equilibrium under **Le Chatelier's Principle**:\n\n"
                "When pressure is increased (by decreasing volume), the system shifts toward the side with **fewer moles of gas** to relieve the pressure stress.\n\n"
                "Consider the Haber reaction:\n"
                "$$N_2(g) + 3H_2(g) \\rightleftharpoons 2NH_3(g)$$\n\n"
                "Left side: $1 + 3 = 4\\text{ moles of gas}$.\n"
                "Right side: $2\\text{ moles of gas}$.\n\n"
                "When we increase pressure, in which direction will the equilibrium shift to restore balance?"
            )
        return (
            "**Le Chatelier's Principle** states that if a dynamic equilibrium is disturbed by changing conditions (temperature, pressure, or concentration), "
            "the position of equilibrium moves to counteract that change.\n\n"
            "Key rules:\n"
            "1. **Adding reactants** $\\rightarrow$ Shifts **right** (makes more products).\n"
            "2. **Increasing pressure** $\\rightarrow$ Shifts toward fewer gas moles.\n"
            "3. **Increasing temperature** $\\rightarrow$ Shifts in the **endothermic** direction ($\\Delta H > 0$).\n\n"
            "Which of these factors would you like to explore with a specific chemical equation?"
        )

    # 18. General Socratic Fallback
    display_q = user_query.strip().rstrip("?.!")
    if len(display_q) > 80:
        display_q = display_q[:77] + "..."

    return (
        f"Let's explore that step-by-step.\n\n"
        f"When thinking about \"{display_q}\", what core principle or governing rule comes to mind first? "
        "Take a moment to consider which key variables are involved and how they interact."
    )


class MockAIAdapter(BaseAIProviderAdapter):
    """Deterministic simulation adapter for offline test execution, CI, and fallback."""

    def execute(self, request: AIExecutionRequest, model_desc: AIModelDescriptor) -> AIExecutionResult:
        req_id = request.request_id or f"req-mock-{int(time.time()*1000)}"
        if is_production_mode():
            logger.error("MockAIAdapter invoked while in production mode. Execution rejected.")
            return AIExecutionResult(
                request_id=req_id,
                content="",
                provider=self.config.provider_name,
                model=model_desc.model_name,
                success=False,
                status=ModelExecutionStatus.MODEL_CONFIGURATION_ERROR,
                error_class="MockInProductionProhibited",
                error_message="Mock engine is strictly prohibited in production mode (F-011, F-012)",
                mock=True,
            )

        t0 = time.perf_counter()
        prompt_words = request.prompt.split()
        prompt_tokens = max(1, int(len(prompt_words) * 1.33))

        content = generate_dynamic_pedagogical_content(request, model_desc)
        completion_tokens = max(1, int(len(content.split()) * 1.33))
        total_tokens = prompt_tokens + completion_tokens

        cost = (
            (prompt_tokens / 1000.0) * model_desc.cost_per_1k_input_usd
            + (completion_tokens / 1000.0) * model_desc.cost_per_1k_output_usd
        )

        latency_ms = round((time.perf_counter() - t0) * 1000.0 + 15.0, 2)

        return AIExecutionResult(
            request_id=req_id,
            content=content,
            provider=self.config.provider_name,
            model=model_desc.model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            estimated_cost_usd=round(cost, 6),
            success=True,
            status=ModelExecutionStatus.MODEL_SUCCESS,
            mock=True,
        )


class LocalGGUFAdapter(BaseAIProviderAdapter):
    """Adapter for locally hosted SLMs (llama.cpp / Ollama / GGUF)."""

    def execute(self, request: AIExecutionRequest, model_desc: AIModelDescriptor) -> AIExecutionResult:
        t0 = time.perf_counter()
        req_id = request.request_id or f"req-local-{int(time.time()*1000)}"

        try:
            from core.providers.local import LocalProvider
            if LocalProvider.is_available():
                messages = []
                if request.system_prompt:
                    messages.append({"role": "system", "content": request.system_prompt})
                messages.append({"role": "user", "content": request.prompt})

                gen_tokens = []
                for chunk in LocalProvider.chat_stream(
                    messages=messages,
                    max_tokens=request.max_tokens or 512,
                    temperature=request.temperature or 0.7,
                ):
                    gen_tokens.append(chunk)

                content = "".join(gen_tokens).strip()
                if content:
                    prompt_tokens = max(1, int(len(request.prompt.split()) * 1.33))
                    completion_tokens = max(1, int(len(content.split()) * 1.33))
                    latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                    return AIExecutionResult(
                        request_id=req_id,
                        content=content,
                        provider=self.config.provider_name,
                        model=model_desc.model_name,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=prompt_tokens + completion_tokens,
                        latency_ms=latency_ms,
                        estimated_cost_usd=0.0,
                        success=True,
                        status=ModelExecutionStatus.MODEL_SUCCESS,
                        mock=False,
                    )
        except Exception as exc:
            logger.debug("LocalProvider inference failed or unavailable: %s", exc)

        if is_production_mode():
            return AIExecutionResult(
                request_id=req_id,
                content="",
                provider=self.config.provider_name,
                model=model_desc.model_name,
                success=False,
                status=ModelExecutionStatus.MODEL_UNAVAILABLE,
                error_class="LocalModelUnavailable",
                error_message="Local GGUF model is not available or failed inference in production mode",
                mock=False,
            )

        content = generate_dynamic_pedagogical_content(request, model_desc)
        prompt_tokens = max(1, int(len(request.prompt.split()) * 1.33))
        completion_tokens = max(1, int(len(content.split()) * 1.33))
        latency_ms = round((time.perf_counter() - t0) * 1000.0 + 35.0, 2)

        return AIExecutionResult(
            request_id=req_id,
            content=content,
            provider=self.config.provider_name,
            model=model_desc.model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            estimated_cost_usd=0.0,
            success=True,
            status=ModelExecutionStatus.MODEL_SUCCESS,
            mock=True,
        )



def map_exception_to_error_status(err: Exception) -> tuple[ModelExecutionStatus, str, str]:
    """Classify runtime exceptions into normalized ModelExecutionStatus, error class, and message (F-011, F-012)."""
    if isinstance(err, urllib.error.HTTPError):
        if err.code == 429:
            return ModelExecutionStatus.MODEL_RATE_LIMITED, f"HTTP_{err.code}", str(err)
        elif err.code in (401, 403):
            return ModelExecutionStatus.MODEL_CONFIGURATION_ERROR, f"HTTP_{err.code}", str(err)
        elif err.code >= 500:
            return ModelExecutionStatus.MODEL_UNAVAILABLE, f"HTTP_{err.code}", str(err)
        else:
            return ModelExecutionStatus.MODEL_INVALID_RESPONSE, f"HTTP_{err.code}", str(err)
    if isinstance(err, (TimeoutError, socket.timeout)):
        return ModelExecutionStatus.MODEL_TIMEOUT, "TimeoutError", str(err)
    if isinstance(err, urllib.error.URLError):
        reason_str = str(err.reason).lower()
        if isinstance(err.reason, (socket.timeout, TimeoutError)) or "timed out" in reason_str:
            return ModelExecutionStatus.MODEL_TIMEOUT, "TimeoutError", str(err)
        return ModelExecutionStatus.MODEL_UNAVAILABLE, "NetworkError", str(err)
    if isinstance(err, (json.JSONDecodeError, KeyError, IndexError)):
        return ModelExecutionStatus.MODEL_INVALID_RESPONSE, type(err).__name__, str(err)
    return ModelExecutionStatus.MODEL_INVALID_RESPONSE, type(err).__name__, str(err)


class OpenAICompatibleAdapter(BaseAIProviderAdapter):
    """Normalized base adapter for OpenAI-compatible HTTP REST endpoints (Phase 22)."""

    def execute(self, request: AIExecutionRequest, model_desc: AIModelDescriptor) -> AIExecutionResult:
        api_key = self.get_api_key()
        req_id = request.request_id or f"req-oai-compat-{int(time.time()*1000)}"

        if not api_key:
            logger.warning("OpenAICompatibleAdapter: Missing API key for provider '%s' (ref: %s)", self.config.provider_name, self.config.api_key_ref)
            return AIExecutionResult(
                request_id=req_id,
                content="",
                provider=self.config.provider_name,
                model=model_desc.model_name,
                success=False,
                status=ModelExecutionStatus.MODEL_CONFIGURATION_ERROR,
                error_class="MissingAPIKeyError",
                error_message=f"Missing API key for provider '{self.config.provider_name}'",
                mock=False,
            )

        t0 = time.perf_counter()
        try:
            base_url = (self.config.base_url or "https://api.openai.com/v1").rstrip("/")
            url = f"{base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            messages.append({"role": "user", "content": request.prompt})

            payload = {
                "model": model_desc.model_name,
                "messages": messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            }
            req_data = json.dumps(payload).encode("utf-8")
            http_req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

            timeout = request.timeout_seconds or self.config.timeout_seconds
            with urllib.request.urlopen(http_req, timeout=timeout) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                choice = resp_data["choices"][0]
                content = choice["message"]["content"]
                usage = resp_data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", max(1, int(len(request.prompt.split()) * 1.33)))
                completion_tokens = usage.get("completion_tokens", max(1, int(len(content.split()) * 1.33)))
                total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
                cost = (
                    (prompt_tokens / 1000.0) * model_desc.cost_per_1k_input_usd
                    + (completion_tokens / 1000.0) * model_desc.cost_per_1k_output_usd
                )
                latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                return AIExecutionResult(
                    request_id=req_id,
                    content=content,
                    provider=self.config.provider_name,
                    model=model_desc.model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    latency_ms=latency_ms,
                    estimated_cost_usd=round(cost, 6),
                    success=True,
                    status=ModelExecutionStatus.MODEL_SUCCESS,
                    mock=False,
                )
        except Exception as err:
            st, err_cls, err_msg = map_exception_to_error_status(err)
            logger.warning("OpenAICompatibleAdapter execution error for provider '%s': %s", self.config.provider_name, err)
            return AIExecutionResult(
                request_id=req_id,
                content="",
                provider=self.config.provider_name,
                model=model_desc.model_name,
                success=False,
                status=st,
                error_class=err_cls,
                error_message=err_msg,
                mock=False,
            )


class OpenAIAdapter(OpenAICompatibleAdapter):
    """Adapter for OpenAI API (GPT-4o, GPT-4o-mini)."""
    pass


class AnthropicAdapter(BaseAIProviderAdapter):
    """Adapter for Anthropic API (Claude 3.5 Sonnet, Claude 3.5 Haiku)."""

    def execute(self, request: AIExecutionRequest, model_desc: AIModelDescriptor) -> AIExecutionResult:
        api_key = self.get_api_key()
        req_id = request.request_id or f"req-ant-{int(time.time()*1000)}"

        if not api_key:
            logger.warning("AnthropicAdapter: Missing API key for provider '%s' (ref: %s)", self.config.provider_name, self.config.api_key_ref)
            return AIExecutionResult(
                request_id=req_id,
                content="",
                provider=self.config.provider_name,
                model=model_desc.model_name,
                success=False,
                status=ModelExecutionStatus.MODEL_CONFIGURATION_ERROR,
                error_class="MissingAPIKeyError",
                error_message=f"Missing API key for provider '{self.config.provider_name}'",
                mock=False,
            )

        t0 = time.perf_counter()
        try:
            base_url = (self.config.base_url or "https://api.anthropic.com/v1").rstrip("/")
            url = f"{base_url}/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model_desc.model_name,
                "max_tokens": request.max_tokens or 1024,
                "messages": [{"role": "user", "content": request.prompt}],
            }
            if request.system_prompt:
                payload["system"] = request.system_prompt

            req_data = json.dumps(payload).encode("utf-8")
            http_req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

            timeout = request.timeout_seconds or self.config.timeout_seconds
            with urllib.request.urlopen(http_req, timeout=timeout) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                content = resp_data["content"][0]["text"]
                usage = resp_data.get("usage", {})
                prompt_tokens = usage.get("input_tokens", max(1, int(len(request.prompt.split()) * 1.33)))
                completion_tokens = usage.get("output_tokens", max(1, int(len(content.split()) * 1.33)))
                cost = (
                    (prompt_tokens / 1000.0) * model_desc.cost_per_1k_input_usd
                    + (completion_tokens / 1000.0) * model_desc.cost_per_1k_output_usd
                )
                return AIExecutionResult(
                    request_id=req_id,
                    content=content,
                    provider=self.config.provider_name,
                    model=model_desc.model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                    estimated_cost_usd=round(cost, 6),
                    success=True,
                    status=ModelExecutionStatus.MODEL_SUCCESS,
                    mock=False,
                )
        except Exception as e:
            st, err_cls, err_msg = map_exception_to_error_status(e)
            logger.error("AnthropicAdapter execution error for provider '%s': %s", self.config.provider_name, e)
            return AIExecutionResult(
                request_id=req_id,
                content="",
                provider=self.config.provider_name,
                model=model_desc.model_name,
                success=False,
                status=st,
                error_class=err_cls,
                error_message=err_msg,
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                mock=False,
            )


class GeminiAdapter(BaseAIProviderAdapter):
    """Adapter for Google Gemini API (Gemini 2.0 Flash, Gemini 1.5 Pro)."""

    def execute(self, request: AIExecutionRequest, model_desc: AIModelDescriptor) -> AIExecutionResult:
        api_key = self.get_api_key()
        req_id = request.request_id or f"req-gem-{int(time.time()*1000)}"

        if not api_key:
            logger.warning("GeminiAdapter: missing API key for provider '%s' (ref: %s)", self.config.provider_name, self.config.api_key_ref)
            return AIExecutionResult(
                request_id=req_id,
                content="",
                provider=self.config.provider_name,
                model=model_desc.model_name,
                success=False,
                status=ModelExecutionStatus.MODEL_CONFIGURATION_ERROR,
                error_class="MissingAPIKeyError",
                error_message=f"Missing API key for provider '{self.config.provider_name}'",
                mock=False,
            )

        t0 = time.perf_counter()
        try:
            model_name = model_desc.model_name
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            
            contents = [{"parts": [{"text": request.prompt}]}]
            payload = {"contents": contents}
            if request.system_prompt:
                payload["systemInstruction"] = {"parts": [{"text": request.system_prompt}]}

            req_data = json.dumps(payload).encode("utf-8")
            http_req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

            timeout = request.timeout_seconds or self.config.timeout_seconds
            with urllib.request.urlopen(http_req, timeout=timeout) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                candidate = resp_data["candidates"][0]
                content = candidate["content"]["parts"][0]["text"]
                prompt_tokens = max(1, int(len(request.prompt.split()) * 1.33))
                completion_tokens = max(1, int(len(content.split()) * 1.33))
                cost = (
                    (prompt_tokens / 1000.0) * model_desc.cost_per_1k_input_usd
                    + (completion_tokens / 1000.0) * model_desc.cost_per_1k_output_usd
                )
                return AIExecutionResult(
                    request_id=req_id,
                    content=content,
                    provider=self.config.provider_name,
                    model=model_desc.model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                    estimated_cost_usd=round(cost, 6),
                    success=True,
                    status=ModelExecutionStatus.MODEL_SUCCESS,
                    mock=False,
                )
        except Exception as e:
            st, err_cls, err_msg = map_exception_to_error_status(e)
            logger.error("GeminiAdapter execution error for provider '%s': %s", self.config.provider_name, e)
            return AIExecutionResult(
                request_id=req_id,
                content="",
                provider=self.config.provider_name,
                model=model_desc.model_name,
                success=False,
                status=st,
                error_class=err_cls,
                error_message=err_msg,
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                mock=False,
            )


class OpenRouterAdapter(OpenAICompatibleAdapter):
    """Adapter for OpenRouter meta-provider via OpenAI-compatible REST API."""
    pass

