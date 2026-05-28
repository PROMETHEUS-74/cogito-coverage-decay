"""
cogito_preferences.py — reconstructed main engine

Reconstruction of the PreferenceAwareCogito loop based on the architectural
description from prior chats. The reconstruction implements the four-step
iterative critique pipeline:

    (1) Generate initial response.
    (2) Score reasoning-pattern coverage of the response against the user's profile.
    (3) If coverage is below target, generate critique focused on top-N preferred
        operators, then revise.
    (4) Iterate until coverage hits target or max iterations is reached.

This file is the implementation behind condition C in the cogito.py experiment
described in the technical article:

    "Coverage decay: when style prompts forget themselves"

The regex patterns are adapted from the CognitoReviewer module, with the
operator set extended from the legacy 9-operator version to the canonical
10-operator experimental profile.

Note:
    This engine was reconstructed from specification, not recovered from the
    original source. Any deviation from prior behaviour should be reported
    transparently in the article's methodology section.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    Anthropic = None  # The caller is expected to handle this at runtime.


# ──────────────────────────────────────────────────────────────────────────────
# Canonical operator set
# ──────────────────────────────────────────────────────────────────────────────

CANONICAL_OPERATORS = {
    "causal",
    "edge_cases",
    "concretize",
    "operationalize",
    "counterfactual",
    "generalize",
    "analogy",
    "decompose",
    "ethical",
    "historical",
}


# The original CognitoReviewer shipped 9 operators including `reframe`.
# The main-engine evidence from prior chats lists 10: causal, edge_cases,
# concretize, operationalize, counterfactual, generalize, analogy, decompose,
# ethical, historical. We adopt the 10-operator canonical set here. `reframe`
# is retained as an optional 11th pattern in case a legacy/live profile uses it.
GOPERATOR_PATTERNS: Dict[str, List[str]] = {
    "causal": [
        r"\b(because|causes?|due to|results? in|leads? to|mechanism|why)\b",
        r"\b(underlying|fundamental|root cause)\b",
    ],
    "edge_cases": [
        r"\b(fails? when|breaks? down|edge case|boundary|exception)\b",
        r"\b(doesn['’]t work if|limitation|caveat|warning)\b",
    ],
    "concretize": [
        r"\b(for example|specifically|concretely|in practice)\b",
        r"\b(let['’]s say|imagine we have|consider the case)\b",
        r"\d+[.,]\d+|\$\d+",
    ],
    "operationalize": [
        r"\b(test|measure|experiment|predict|validate)\b",
        r"\b(observable|measurable|falsifiable)\b",
    ],
    "counterfactual": [
        r"\b(what if|suppose|imagine if|alternatively)\b",
        r"\b(had .* been|were .* to)\b",
    ],
    "generalize": [
        r"\b(in general|broadly|abstract|principle|pattern)\b",
        r"\b(applies to|extends to|more generally)\b",
    ],
    "analogy": [
        r"\b(like|similar to|analogous|metaphor|just as)\b",
        r"\b(think of it as|imagine .* as)\b",
    ],
    "decompose": [
        r"\b(component|part|element|piece|sub-?problem)\b",
        r"\b(break (?:this )?down|breaking down|decompose|break into)\b",
    ],
    "ethical": [
        r"\b(should|ought|right|wrong|ethical|moral)\b",
        r"\b(responsibility|fairness|harm|benefit)\b",
    ],
    "historical": [
        r"\b(historically|originally|over time|evolved|precedent)\b",
        r"\b(in the past|context for this|how we got here)\b",
    ],
    # Optional 11th — only scored if present in the profile.
    "reframe": [
        r"\b(another way|different perspective|flip this|reframe)\b",
        r"\b(instead of|rather than|consider viewing)\b",
    ],
}


# ──────────────────────────────────────────────────────────────────────────────
# Profile validation
# ──────────────────────────────────────────────────────────────────────────────


def validate_profile_dict(data: Dict[str, float]) -> None:
    """
    Strict validation of a profile dict.

    Catches silent failures:
        - typos in operator names, e.g. "edge_case" instead of "edge_cases";
        - missing canonical operators;
        - non-numeric or out-of-range values.

    `reframe` is allowed as an optional 11th operator but is not required.
    """
    allowed = CANONICAL_OPERATORS | {"reframe"}
    unknown = set(data) - allowed
    missing = CANONICAL_OPERATORS - set(data)

    if unknown:
        raise ValueError(f"Unknown profile operators: {sorted(unknown)}")

    if missing:
        raise ValueError(f"Missing canonical operators: {sorted(missing)}")

    for op, value in data.items():
        if value is None:
            continue

        if not isinstance(value, (int, float)):
            raise ValueError(
                f"Profile value for {op!r} must be numeric, "
                f"got {type(value).__name__}"
            )

        if not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"Profile value for {op!r} must be in [0, 1], got {value}")


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class GOperatorPreferences:
    """Ten-dimensional cognitive profile. Values are in the range 0.0–1.0."""

    causal: float = 0.5
    edge_cases: float = 0.5
    concretize: float = 0.5
    operationalize: float = 0.5
    counterfactual: float = 0.5
    generalize: float = 0.5
    analogy: float = 0.5
    decompose: float = 0.5
    ethical: float = 0.5
    historical: float = 0.5
    reframe: Optional[float] = None  # Optional 11th — see notes above.

    def to_dict(self) -> Dict[str, float]:
        """Return profile as a dict, omitting absent optional operators."""
        d = asdict(self)
        if d.get("reframe") is None:
            d.pop("reframe", None)
        return d

    @classmethod
    def from_dict(
        cls, data: Dict[str, float], strict: bool = False
    ) -> "GOperatorPreferences":
        """
        Construct profile from a dict.

        If strict=True, validate that all canonical operators are present,
        no unknown operators are present, and all values are numeric in [0, 1].
        """
        if strict:
            validate_profile_dict(data)

        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def top_n(self, n: int = 3, threshold: float = 0.65) -> List[Tuple[str, float]]:
        """Return the top-N preferred operators above a threshold."""
        items = [
            (k, v)
            for k, v in self.to_dict().items()
            if v is not None and v >= threshold
        ]
        items.sort(key=lambda kv: kv[1], reverse=True)
        return items[:n]


@dataclass
class IterationState:
    """Snapshot of a single iteration of the Cogito loop."""

    iteration: int
    answer: str
    coverage: Dict[str, float]
    weighted_coverage: float
    critique: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class CogitoResult:
    """Result of a full Cogito run — all iterations and the final answer."""

    question: str
    final_answer: str
    iterations: List[IterationState]
    converged: bool
    target_coverage: float
    profile: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the result to plain JSON-compatible structures."""
        return {
            "question": self.question,
            "final_answer": self.final_answer,
            "iterations": [
                {
                    "iteration": s.iteration,
                    "answer": s.answer,
                    "coverage": s.coverage,
                    "weighted_coverage": s.weighted_coverage,
                    "critique": s.critique,
                    "timestamp": s.timestamp,
                }
                for s in self.iterations
            ],
            "converged": self.converged,
            "target_coverage": self.target_coverage,
            "profile": self.profile,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Coverage detection
# ──────────────────────────────────────────────────────────────────────────────


def detect_operator_density(text: str, operator: str) -> float:
    """
    Density of an operator's lexical markers in a text, normalised to [0, 1].

    Density = (number of distinct matched regex patterns for this operator)
              / (number of regex patterns defined for this operator)

    This produces a smoother signal than a binary "is the operator present"
    detector. It remains a proxy: it detects style markers associated with
    reasoning patterns, not reasoning itself.
    """
    patterns = GOPERATOR_PATTERNS.get(operator, [])

    if not patterns:
        return 0.0

    text_lower = text.lower()
    matched = sum(1 for pattern in patterns if re.search(pattern, text_lower))
    return matched / len(patterns)


def score_coverage(text: str, profile: GOperatorPreferences) -> Dict[str, float]:
    """Return per-operator coverage for every operator in the profile."""
    return {
        operator: detect_operator_density(text, operator)
        for operator, weight in profile.to_dict().items()
        if weight is not None
    }


def weighted_coverage(
    coverage: Dict[str, float], profile: GOperatorPreferences
) -> float:
    """
    Single scalar measuring how well the response matched the user's preferences.

    Weighted average of per-operator coverage, weighted by the user's stated
    preference for that operator. Low-priority operators contribute less;
    high-priority missing operators drag the score down.
    """
    weights = profile.to_dict()
    weighted_sum = 0.0
    total_weight = 0.0

    for operator, cov in coverage.items():
        weight = weights.get(operator)

        if weight is None:
            continue

        weighted_sum += cov * weight
        total_weight += weight

    if total_weight == 0.0:
        return 0.0

    return weighted_sum / total_weight


def coverage_by_paragraph(
    text: str, profile: GOperatorPreferences
) -> List[Dict[str, float]]:
    """
    Return one per-operator coverage dict per paragraph.

    Used for detailed analysis of which operators decay by paragraph position.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return [score_coverage(paragraph, profile) for paragraph in paragraphs]


def weighted_coverage_by_paragraph(
    text: str, profile: GOperatorPreferences
) -> List[float]:
    """
    Return one weighted coverage score per paragraph.

    This directly supports the article's Chart 1: coverage by paragraph position.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return [
        weighted_coverage(score_coverage(paragraph, profile), profile)
        for paragraph in paragraphs
    ]


def count_operator_hits(text: str, operator: str) -> int:
    """
    Total number of marker matches for an operator in a text.

    Unlike `detect_operator_density`, which counts distinct regex patterns
    matched and therefore saturates quickly, this counts every occurrence of
    every marker. It supports the length-sensitive robustness check.
    """
    patterns = GOPERATOR_PATTERNS.get(operator, [])
    text_lower = text.lower()
    return sum(len(re.findall(pattern, text_lower)) for pattern in patterns)


def weighted_marker_hits_per_500w(text: str, profile: GOperatorPreferences) -> float:
    """
    Length-normalised marker density: preference-weighted marker hits per 500 words.

    This is reported alongside `coverage_weighted` as a robustness check, not as
    the headline metric.

    Note:
        Normalising by total_weight means this metric responds to changes in
        profile spread as well as content. That is acceptable for a robustness
        check; `coverage_weighted` remains the protocol-locked headline measure.
    """
    weights = profile.to_dict()
    word_count = max(len(text.split()), 1)

    weighted_hits = 0.0
    total_weight = 0.0

    for operator, weight in weights.items():
        if weight is None:
            continue

        hits = count_operator_hits(text, operator)
        weighted_hits += hits * weight
        total_weight += weight

    if total_weight == 0.0:
        return 0.0

    return (weighted_hits / total_weight) / (word_count / 500.0)


def response_stats(text: str, profile: GOperatorPreferences) -> Dict[str, Any]:
    """
    Length-aware stats for a single response.

    The headline metric for the experiment is `coverage_weighted`;
    `weighted_marker_hits_per_500w` is reported alongside as a length-sensitive
    robustness check.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    coverage_raw = score_coverage(text, profile)

    return {
        "word_count": len(text.split()),
        "paragraph_count": len(paragraphs),
        "coverage_raw": coverage_raw,
        "coverage_weighted": weighted_coverage(coverage_raw, profile),
        "coverage_by_paragraph": coverage_by_paragraph(text, profile),
        "weighted_coverage_by_paragraph": weighted_coverage_by_paragraph(text, profile),
        "weighted_marker_hits_per_500w": weighted_marker_hits_per_500w(text, profile),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Prompts for the Cogito loop
# ──────────────────────────────────────────────────────────────────────────────


CRITIQUE_PROMPT_TEMPLATE = """You are reviewing an answer for whether it sufficiently reflects a specific user's reasoning style.

The user's top reasoning preferences, and their strength from 0 to 1, are:
{top_operators}

The answer being reviewed:
----
{answer}
----

Pattern-coverage analysis, per operator from 0 to 1, using a regex-based proxy:
{coverage_summary}

Your task:
Identify the THREE most important ways this answer could be revised to better match the user's reasoning preferences.

Focus only on the user's TOP preferences listed above. Be specific:
- name the operator;
- name the part of the answer that is weak on it;
- say what would strengthen it.

Do not rewrite the answer.
Produce only the critique."""


REFINE_PROMPT_TEMPLATE = """Revise this answer to better match the user's reasoning preferences.

User's top reasoning preferences:
{top_operators}

Original answer:
----
{answer}
----

Critique:
----
{critique}
----

Produce a revised version of the answer.

Constraints:
- Keep the answer's substance roughly the same.
- Keep the length roughly the same.
- Strengthen the reasoning patterns named in the critique.
- Do not inflate the answer with unnecessary filler.
- Do not narrate the revision.

Produce only the revised answer."""


# ──────────────────────────────────────────────────────────────────────────────
# The Cogito loop
# ──────────────────────────────────────────────────────────────────────────────


class PreferenceAwareCogito:
    """
    Main Cogito engine.

    Runs the iterative critique loop:
        generate → score → critique → refine → repeat
    """

    def __init__(
        self,
        profile: GOperatorPreferences,
        client: Optional[Any] = None,
        model_generate: str = "claude-sonnet-4-6",
        model_critique: str = "claude-sonnet-4-6",
        target_coverage: float = 0.75,
        max_iterations: int = 3,
        max_tokens: int = 900,
        temperature_generate: float = 0.3,
        temperature_critique: float = 0.2,
        top_n_operators: int = 3,
        max_retries: int = 3,
        retry_backoff_seconds: float = 2.0,
        verbose: bool = False,
    ):
        """
        Args:
            profile:
                User reasoning-pattern preference profile.
            client:
                Optional Anthropic-compatible client. If omitted, Anthropic()
                is constructed from environment configuration.
            model_generate:
                Model ID used for generation/refinement.
            model_critique:
                Model ID used for critique.
            target_coverage:
                Default 0.75, matching the pre-registered protocol. The weighted
                score is a normalised weighted average in [0, 1].
            max_iterations:
                Maximum critique/refinement rounds after the initial answer.
            max_tokens:
                900 targets the 500–700 word answer-length band while leaving
                some headroom.
            temperature_generate:
                Low generation temperature to reduce experimental variance.
            temperature_critique:
                Lower critique temperature for more deterministic reviews.
            top_n_operators:
                Number of strongest operators to focus critique/refinement on.
            max_retries:
                Number of attempts for transient API failures.
            retry_backoff_seconds:
                Base exponential backoff delay for retry attempts.
            verbose:
                Print progress logs if True.
        """
        if Anthropic is None and client is None:
            raise RuntimeError(
                "The `anthropic` package is not installed and no client was provided. "
                "Install with `pip install anthropic`, or pass a custom client."
            )

        self.client = client if client is not None else Anthropic()
        self.profile = profile
        self.model_generate = model_generate
        self.model_critique = model_critique
        self.target_coverage = target_coverage
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.temperature_generate = temperature_generate
        self.temperature_critique = temperature_critique
        self.top_n_operators = top_n_operators
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.verbose = verbose

    # ── private helpers ──────────────────────────────────────────────────────

    def _log(self, message: str) -> None:
        if self.verbose:
            print(f"[cogito] {message}")

    def _call_model(
        self,
        model: str,
        system: Optional[str],
        user: str,
        temperature: float,
    ) -> str:
        """
        Call the Anthropic Messages API with basic retry handling.

        This keeps long experiment runs from failing permanently due to a single
        transient API/network issue.
        """
        kwargs = {
            "model": model,
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": user}],
        }

        if system:
            kwargs["system"] = system

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                response = self.client.messages.create(**kwargs)

                parts: List[str] = []
                for block in response.content:
                    text = getattr(block, "text", None)
                    if text:
                        parts.append(text)

                return "".join(parts).strip()

            except Exception as exc:  # pragma: no cover - depends on API runtime
                last_error = exc
                if attempt < self.max_retries - 1:
                    sleep_seconds = self.retry_backoff_seconds ** attempt
                    self._log(
                        f"model call failed on attempt {attempt + 1}/"
                        f"{self.max_retries}: {exc}; retrying in {sleep_seconds:.1f}s"
                    )
                    time.sleep(sleep_seconds)

        raise RuntimeError(f"Model call failed after {self.max_retries} attempts: {last_error}")

    def _format_top_operators(self) -> str:
        top = self.profile.top_n(self.top_n_operators)

        if not top:
            # Fallback: top N by raw weight even below threshold.
            top = sorted(
                (
                    (operator, weight)
                    for operator, weight in self.profile.to_dict().items()
                    if weight is not None
                ),
                key=lambda kv: kv[1],
                reverse=True,
            )[: self.top_n_operators]

        return "\n".join(f"  • {operator} ({weight:.2f})" for operator, weight in top)

    def _format_coverage_summary(self, coverage: Dict[str, float]) -> str:
        return "\n".join(
            f"  • {operator}: {cov:.2f}"
            for operator, cov in sorted(
                coverage.items(), key=lambda kv: kv[1], reverse=True
            )
        )

    def _format_full_profile(self) -> str:
        """
        Return all operators with weights, sorted high to low.

        Used in the system prompt so condition B and condition C receive the
        same information content the coverage scorer uses.
        """
        items = sorted(
            (
                (operator, weight)
                for operator, weight in self.profile.to_dict().items()
                if weight is not None
            ),
            key=lambda kv: kv[1],
            reverse=True,
        )
        return "\n".join(f"  • {operator}: {weight:.2f}" for operator, weight in items)

    # ── public API ───────────────────────────────────────────────────────────

    def build_system_prompt(self) -> str:
        """
        Build the cognitive-profile system prompt.

        This exact prompt should be used in BOTH:
            - condition B: system prompt only, no iteration;
            - condition C: same prompt plus iterative critique/refinement.

        That preserves the experimental comparison:
            B = preference description only.
            C = same preference description + application/verification loop.
        """
        lines = [
            "You are answering questions in a way that reflects this user's "
            "cognitive preferences.",
            "",
            "Full reasoning-pattern profile, with preference weights from "
            "0 (irrelevant) to 1 (essential):",
            "",
            self._format_full_profile(),
            "",
            "Highest-priority reasoning patterns to emphasise:",
            self._format_top_operators(),
            "",
            "Bring these patterns through across the entire answer, not just "
            "the opening paragraph. Maintain them through to the end.",
        ]
        return "\n".join(lines)

    def generate_initial(self, question: str) -> str:
        """Generate the first-pass answer using the profile system prompt."""
        return self._call_model(
            model=self.model_generate,
            system=self.build_system_prompt(),
            user=question,
            temperature=self.temperature_generate,
        )

    def critique(self, answer: str, coverage: Dict[str, float]) -> str:
        """Generate a critique focused on the top preferred operators."""
        prompt = CRITIQUE_PROMPT_TEMPLATE.format(
            top_operators=self._format_top_operators(),
            answer=answer,
            coverage_summary=self._format_coverage_summary(coverage),
        )
        return self._call_model(
            model=self.model_critique,
            system=None,
            user=prompt,
            temperature=self.temperature_critique,
        )

    def refine(self, answer: str, critique: str) -> str:
        """Revise the answer using the critique."""
        prompt = REFINE_PROMPT_TEMPLATE.format(
            top_operators=self._format_top_operators(),
            answer=answer,
            critique=critique,
        )
        return self._call_model(
            model=self.model_generate,
            system=None,
            user=prompt,
            temperature=self.temperature_generate,
        )

    def run(self, question: str) -> CogitoResult:
        """Run the full Cogito loop on a single question."""
        self._log(f"Q: {question[:60]}{'…' if len(question) > 60 else ''}")

        iterations: List[IterationState] = []

        # Iteration 0 — initial answer.
        answer = self.generate_initial(question)
        coverage = score_coverage(answer, self.profile)
        current_weighted_coverage = weighted_coverage(coverage, self.profile)

        self._log(f"  iter 0: weighted_coverage={current_weighted_coverage:.3f}")

        iterations.append(
            IterationState(
                iteration=0,
                answer=answer,
                coverage=coverage,
                weighted_coverage=current_weighted_coverage,
            )
        )

        if current_weighted_coverage >= self.target_coverage:
            return CogitoResult(
                question=question,
                final_answer=answer,
                iterations=iterations,
                converged=True,
                target_coverage=self.target_coverage,
                profile=self.profile.to_dict(),
            )

        # Iterative critique-and-refine.
        for i in range(1, self.max_iterations + 1):
            critique_text = self.critique(answer, coverage)
            refined = self.refine(answer, critique_text)

            new_coverage = score_coverage(refined, self.profile)
            new_weighted_coverage = weighted_coverage(new_coverage, self.profile)

            self._log(f"  iter {i}: weighted_coverage={new_weighted_coverage:.3f}")

            # Record the attempt regardless of acceptance. The critique is
            # attached to the iteration it produced.
            iterations.append(
                IterationState(
                    iteration=i,
                    answer=refined,
                    coverage=new_coverage,
                    weighted_coverage=new_weighted_coverage,
                    critique=critique_text,
                )
            )

            # Monotonic acceptance: only advance the working answer if the
            # refined version scores at least as well as the current answer.
            if new_weighted_coverage >= current_weighted_coverage:
                answer = refined
                coverage = new_coverage
                current_weighted_coverage = new_weighted_coverage
            else:
                self._log(f"  iter {i}: regression — keeping previous working answer")

            if current_weighted_coverage >= self.target_coverage:
                return CogitoResult(
                    question=question,
                    final_answer=answer,
                    iterations=iterations,
                    converged=True,
                    target_coverage=self.target_coverage,
                    profile=self.profile.to_dict(),
                )

        # Did not converge — return the best iteration observed.
        best = max(iterations, key=lambda state: state.weighted_coverage)

        return CogitoResult(
            question=question,
            final_answer=best.answer,
            iterations=iterations,
            converged=False,
            target_coverage=self.target_coverage,
            profile=self.profile.to_dict(),
        )


# ──────────────────────────────────────────────────────────────────────────────
# Convenience constructors
# ──────────────────────────────────────────────────────────────────────────────


def load_profile(path: str) -> GOperatorPreferences:
    """
    Load a profile JSON.

    Accepts either:
        {operator: weight}
    or the structured legacy reviewer format:
        {"g_operators": {operator: weight}}

    Validation is strict: unknown or missing operators raise rather than
    silently defaulting to 0.5.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "g_operators" in data:
        data = data["g_operators"]

    return GOperatorPreferences.from_dict(data, strict=True)


# ──────────────────────────────────────────────────────────────────────────────
# Quick self-test — no API call.
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample = (
        "The system fails when concurrent writes exceed the lock budget, "
        "because the underlying mechanism uses a single mutex. For example, "
        "if 16 threads each try to write 1.5 MB simultaneously, the queue "
        "saturates. Specifically, the failure mode is observable when "
        "throughput plateaus despite increasing thread count."
    )

    profile = GOperatorPreferences(
        causal=0.90,
        edge_cases=0.85,
        concretize=0.75,
        operationalize=0.65,
        counterfactual=0.60,
        generalize=0.65,
        analogy=0.20,
        decompose=0.75,
        ethical=0.20,
        historical=0.30,
    )

    coverage = score_coverage(sample, profile)
    weighted = weighted_coverage(coverage, profile)
    stats = response_stats(sample, profile)

    print("Per-operator coverage:")
    for operator, cov in sorted(coverage.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {operator:>16}: {cov:.2f}")

    print(f"\nWeighted coverage:                {weighted:.3f}")
    print(f"Weighted coverage by paragraph:   {stats['weighted_coverage_by_paragraph']}")
    print(f"Marker hits per 500 words:        {stats['weighted_marker_hits_per_500w']:.3f}")
    print(f"Top-3 preferences:                {profile.top_n(3)}")
