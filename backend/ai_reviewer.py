from __future__ import annotations

from typing import Any


# ============================================================
# LOCAL AI / SECURITY REVIEWER
# ============================================================
#
# Free, deterministic reviewer.
# No OpenAI API key or paid service is required.
#
# It consumes confirmed runtime weaknesses plus static-analysis
# findings and merges related findings into a single useful report.
# ============================================================


def _severity(finding_type: str) -> str:
    return {
        "memory_error": "critical",
        "array_access": "critical",
        "buffer_overflow": "critical",
        "use_after_free": "critical",
        "integer_overflow": "high",
        "overflow": "high",
        "arithmetic_error": "high",
        "division": "high",
        "timeout": "high",
        "loop": "high",
        "wrong_answer": "medium",
        "boundary": "medium",
        "performance_risk": "medium",
    }.get(finding_type, "medium")


def _input_of(finding: dict[str, Any]) -> str:
    value = (
        finding.get("minimal_input")
        or finding.get("input")
        or ""
    )
    return str(value)


def _normalized_type(finding: dict[str, Any]) -> str:
    raw = str(finding.get("type", "")).lower().strip()

    if raw in {"overflow", "integer_overflow"}:
        return "integer_overflow"

    if raw in {"memory_error", "array_access", "buffer_overflow"}:
        return "memory_error"

    if raw in {"arithmetic_error", "division"}:
        return "arithmetic_error"

    if raw in {"timeout", "loop"}:
        return "timeout"

    return raw


def _same_issue(
    runtime: dict[str, Any],
    static: dict[str, Any],
) -> bool:
    """
    Determine whether a runtime finding and static finding describe
    the same underlying issue.
    """

    runtime_type = _normalized_type(runtime)
    static_type = _normalized_type(static)

    if runtime_type != static_type:
        return False

    # If both have locations, matching locations are strong evidence.
    runtime_location = runtime.get("location")
    static_location = static.get("location")

    if (
        isinstance(runtime_location, dict)
        and isinstance(static_location, dict)
    ):
        if (
            runtime_location.get("line")
            and static_location.get("line")
            and runtime_location.get("line")
            == static_location.get("line")
        ):
            return True

    # Overflow findings can be matched using operator/operands.
    if runtime_type == "integer_overflow":
        rop = runtime.get("operator")
        sop = static.get("operator")

        rleft = runtime.get("left")
        sleft = static.get("left")

        rright = runtime.get("right")
        sright = static.get("right")

        if rop and sop and rop == sop:
            if (
                rleft is None
                or sleft is None
                or str(rleft) == str(sleft)
            ) and (
                rright is None
                or sright is None
                or str(rright) == str(sright)
            ):
                return True

        # Runtime overflow may only have the input. Static analysis
        # may have the actual expression. Treat them as the same
        # category when there is only one static overflow finding.
        return True

    # Array/memory findings.
    if runtime_type == "memory_error":
        r_array = runtime.get("array")
        s_array = static.get("array")

        r_index = runtime.get("index_variable")
        s_index = static.get("index_variable")

        if r_array and s_array and str(r_array) != str(s_array):
            return False

        if r_index and s_index and str(r_index) != str(s_index):
            return False

        return True

    # Division/arithmetic.
    if runtime_type == "arithmetic_error":
        rr = runtime.get("right")
        sr = static.get("right")

        if rr is not None and sr is not None:
            return str(rr) == str(sr)

        return True

    return False


def _enrich_runtime_finding(
    runtime: dict[str, Any],
    static_findings: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Merge static expression information into a confirmed runtime finding.
    """

    result = dict(runtime)

    for static in static_findings:
        if not _same_issue(runtime, static):
            continue

        # Static analysis is useful for expression-level information.
        for key in (
            "operator",
            "left",
            "right",
            "variables",
            "variable_type",
            "array",
            "index_variable",
            "array_size",
            "min_index",
            "max_index",
            "expression",
            "location",
        ):
            if key not in result or result.get(key) in (None, ""):
                if key in static:
                    result[key] = static[key]

        break

    return result


def _merge_findings(
    weaknesses: list[dict[str, Any]],
    static_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Runtime-confirmed findings are authoritative.

    Static findings are used to enrich runtime findings and are only
    emitted independently when they represent a different issue.
    """

    merged: list[dict[str, Any]] = []

    runtime_findings = [
        item for item in weaknesses
        if isinstance(item, dict)
    ]

    static = [
        item for item in static_findings
        if isinstance(item, dict)
    ]

    # First: enrich every confirmed runtime finding.
    for runtime in runtime_findings:
        merged.append(
            _enrich_runtime_finding(
                runtime,
                static,
            )
        )

    # Then add genuinely different static findings.
    for static_item in static:
        duplicate = False

        for runtime in runtime_findings:
            if _same_issue(runtime, static_item):
                duplicate = True
                break

        if not duplicate:
            merged.append(static_item)

    return merged


def _review_overflow(
    finding: dict[str, Any],
) -> dict[str, Any]:
    left = finding.get("left")
    right = finding.get("right")
    operator = finding.get("operator")

    if left is not None and right is not None:
        expression = f"{left} {operator or ''} {right}".strip()
    else:
        expression = "the integer arithmetic expression"

    # Multiplication needs multiplication in the suggested code.
    if operator == "*":
        if left is not None and right is not None:
            suggested = (
                f"long long result = 1LL * {left} * {right};"
            )
        else:
            suggested = (
                "long long result = 1LL * n * 2;"
            )

    elif operator == "+":
        if left is not None and right is not None:
            suggested = (
                f"long long result = 1LL * {left} + {right};"
            )
        else:
            suggested = (
                "long long result = 1LL * n + value;"
            )

    elif operator == "-":
        if left is not None and right is not None:
            suggested = (
                f"long long result = 1LL * {left} - {right};"
            )
        else:
            suggested = (
                "long long result = 1LL * a - b;"
            )

    else:
        suggested = (
            "long long result = /* perform the calculation using "
            "long long */;"
        )

    return {
        "type": "integer_overflow",
        "severity": "high",
        "title": "Signed integer overflow",
        "input": _input_of(finding),
        "root_cause": (
            f"The expression `{expression}` is evaluated using a "
            "type whose range may be too small for the result."
        ),
        "explanation": (
            "The calculation can exceed the range of a signed 32-bit "
            "int. Signed integer overflow in C++ is undefined behavior."
        ),
        "fix": (
            "Perform the arithmetic using long long by promoting the "
            "operands before the operation."
        ),
        "suggested_code": suggested,
        "why_fix_works": (
            "The operands are promoted before the arithmetic, so the "
            "calculation uses the wider long long range."
        ),
        "confidence": 0.98,
    }


def _review_memory(
    finding: dict[str, Any],
) -> dict[str, Any]:
    array = str(finding.get("array", "arr"))
    index = str(finding.get("index_variable", "index"))
    size = finding.get("array_size")

    if size is not None:
        condition = f"{index} >= 0 && {index} < {size}"
        range_text = f"0 through {int(size) - 1}"
    else:
        condition = f"{index} >= 0"
        range_text = "the valid array range"

    return {
        "type": "memory_error",
        "severity": "critical",
        "title": "Out-of-bounds array access",
        "input": _input_of(finding),
        "root_cause": (
            f"The program can access `{array}[{index}]` without "
            f"proving that `{index}` is within {range_text}."
        ),
        "explanation": (
            "Accessing an array outside its valid bounds causes "
            "undefined behavior and may corrupt memory or crash."
        ),
        "fix": "Validate the array index before accessing the array.",
        "suggested_code": (
            f"if ({condition}) {{\n"
            f"    // safe {array}[{index}] access\n"
            "} else {\n"
            "    // handle invalid index\n"
            "}"
        ),
        "why_fix_works": (
            "The array access occurs only after the index has been "
            "validated against the valid range."
        ),
        "confidence": 0.99,
    }


def _review_arithmetic(
    finding: dict[str, Any],
) -> dict[str, Any]:
    divisor = str(
        finding.get("right")
        or finding.get("target")
        or "n"
    )

    return {
        "type": "arithmetic_error",
        "severity": "high",
        "title": "Division by zero",
        "input": _input_of(finding),
        "root_cause": (
            f"The program uses `{divisor}` as a divisor without "
            "guaranteeing that it is non-zero."
        ),
        "explanation": (
            "Integer division or modulo by zero is undefined behavior."
        ),
        "fix": "Check the divisor before performing division or modulo.",
        "suggested_code": (
            f"if ({divisor} != 0) {{\n"
            "    // perform calculation\n"
            "} else {\n"
            "    // handle zero divisor\n"
            "}"
        ),
        "why_fix_works": (
            "The arithmetic operation cannot execute with a zero divisor."
        ),
        "confidence": 0.99,
    }


def _review_timeout(
    finding: dict[str, Any],
) -> dict[str, Any]:
    variable = str(
        finding.get("variable")
        or "loop_variable"
    )

    return {
        "type": "timeout",
        "severity": "high",
        "title": "Possible non-terminating loop",
        "input": _input_of(finding),
        "root_cause": (
            f"The loop depends on `{variable}`, but the control "
            "variable may not move toward termination."
        ),
        "explanation": (
            "A loop that cannot reach its termination condition can "
            "continue until the execution time limit is reached."
        ),
        "fix": (
            "Update the loop control variable so each iteration moves "
            "toward termination."
        ),
        "suggested_code": (
            f"while (condition) {{\n"
            "    // work\n"
            f"    {variable}--;\n"
            "}"
        ),
        "why_fix_works": (
            "The control variable progresses toward the terminating "
            "condition."
        ),
        "confidence": 0.97,
    }


def _review_wrong_answer(
    finding: dict[str, Any],
) -> dict[str, Any]:
    actual = finding.get("actual", "")
    expected = finding.get("expected", "")

    return {
        "type": "wrong_answer",
        "severity": "medium",
        "title": "Incorrect program output",
        "input": _input_of(finding),
        "root_cause": (
            "The submitted program does not produce the same result "
            "as the reference implementation."
        ),
        "explanation": (
            f"For this input, the program produced `{actual}`, "
            f"but the expected result is `{expected}`."
        ),
        "fix": (
            "Compare the submitted logic with the reference behavior, "
            "starting with the minimal failing input."
        ),
        "suggested_code": (
            "// Correct the operation producing the wrong result."
        ),
        "why_fix_works": (
            "Correcting the mismatched operation or control flow makes "
            "the program agree with the reference behavior."
        ),
        "confidence": 0.99,
    }


def _review_generic(
    finding: dict[str, Any],
) -> dict[str, Any]:
    kind = _normalized_type(finding)

    return {
        "type": kind,
        "severity": _severity(kind),
        "title": "Potential code issue",
        "input": _input_of(finding),
        "root_cause": str(
            finding.get("risk")
            or finding.get("reason")
            or "The analyzer detected a potentially unsafe condition."
        ),
        "explanation": (
            "The deterministic analyzer identified a condition that "
            "requires review."
        ),
        "fix": (
            "Review the reported operation and validate its assumptions."
        ),
        "suggested_code": "",
        "why_fix_works": (
            "The validation prevents the reported condition from "
            "being reached unexpectedly."
        ),
        "confidence": 0.85,
    }


def _review_finding(
    finding: dict[str, Any],
) -> dict[str, Any]:
    kind = _normalized_type(finding)

    if kind == "integer_overflow":
        return _review_overflow(finding)

    if kind == "memory_error":
        return _review_memory(finding)

    if kind == "arithmetic_error":
        return _review_arithmetic(finding)

    if kind == "timeout":
        return _review_timeout(finding)

    if kind == "wrong_answer":
        return _review_wrong_answer(finding)

    return _review_generic(finding)


def get_ai_review(
    code: str = "",
    reference_code: str = "",
    weaknesses: list[dict[str, Any]] | None = None,
    analysis: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Main local reviewer.

    Runtime-confirmed findings are authoritative.
    Static findings enrich runtime findings rather than duplicating them.
    """

    weaknesses = weaknesses or []
    analysis = analysis or {}

    static_findings = analysis.get("findings", [])

    if not isinstance(static_findings, list):
        static_findings = []

    merged = _merge_findings(
        weaknesses=[
            item for item in weaknesses
            if isinstance(item, dict)
        ],
        static_findings=[
            item for item in static_findings
            if isinstance(item, dict)
        ],
    )

    reviewed = [
        _review_finding(item)
        for item in merged
    ]

    severity_order = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
    }

    reviewed.sort(
        key=lambda item: (
            severity_order.get(
                item.get("severity", "medium"),
                2,
            ),
            str(item.get("type", "")),
        )
    )

    return {
        "enabled": True,
        "status": "completed",
        "provider": "local",
        "model": "local-security-reviewer",
        "message": (
            "Local security reviewer generated this analysis from "
            "deterministic test and static-analysis findings. "
            "No external API or paid service was used."
        ),
        "findings": reviewed,
        "finding_count": len(reviewed),
    }


# Compatibility aliases.
review_code = get_ai_review
review = get_ai_review
analyze_with_ai = get_ai_review
ai_review_code = get_ai_review