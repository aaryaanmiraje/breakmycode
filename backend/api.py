from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai_reviewer import get_ai_review
from generator import analyze_code, generate_test_inputs


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Break My Code API",
    version="3.1.0",
    description="Automated C++ code analysis and testing API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODEL
# ============================================================

class AnalyzeRequest(BaseModel):
    code: str
    reference_code: str | None = None


# ============================================================
# CONFIGURATION
# ============================================================

MAX_TESTS = 30
COMPILE_TIMEOUT = 15
RUN_TIMEOUT = 2.0


# ============================================================
# BASIC ROUTES
# ============================================================

@app.get("/")
def root():
    return {
        "name": "Break My Code API",
        "version": "3.1.0",
        "status": "running",
        "features": [
            "static_analysis",
            "test_generation",
            "runtime_testing",
            "differential_testing",
            "sanitizer_detection",
            "timeout_detection",
            "failure_classification",
            "ai_review",
        ],
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
    }


# ============================================================
# COMPILER
# ============================================================

def find_compiler() -> str:
    """Find an available C++ compiler."""

    for compiler in (
        "g++",
        "clang++",
        "c++",
    ):
        path = shutil.which(compiler)

        if path:
            return path

    raise RuntimeError(
        "No C++ compiler found. Install g++ or clang++."
    )


def compile_cpp(
    code: str,
    executable: str,
    sanitizer: bool = False,
) -> tuple[bool, str]:

    compiler = find_compiler()

    source_file = executable + ".cpp"

    with open(
        source_file,
        "w",
        encoding="utf-8",
    ) as file:
        file.write(code)

    flags = [
        "-std=c++17",
        "-O0",
        "-g",
        "-Wall",
        "-Wextra",
    ]

    if sanitizer:
        flags.extend(
            [
                "-fsanitize=address,undefined",
                "-fno-omit-frame-pointer",
            ]
        )

    command = [
        compiler,
        source_file,
        "-o",
        executable,
        *flags,
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=COMPILE_TIMEOUT,
        )

    except subprocess.TimeoutExpired:
        return (
            False,
            "Compilation timed out.",
        )

    if result.returncode != 0:
        return (
            False,
            result.stderr.strip(),
        )

    return True, ""


# ============================================================
# PROGRAM EXECUTION
# ============================================================

def run_program(
    executable: str,
    input_data: str,
    timeout: float = RUN_TIMEOUT,
) -> dict[str, Any]:

    started = time.perf_counter()

    try:
        result = subprocess.run(
            [executable],
            input=input_data + "\n",
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        runtime = (
            time.perf_counter() - started
        )

        return {
            "status": "completed",
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "runtime": runtime,
        }

    except subprocess.TimeoutExpired:

        runtime = (
            time.perf_counter() - started
        )

        return {
            "status": "timeout",
            "returncode": None,
            "stdout": "",
            "stderr": "Execution timed out.",
            "runtime": runtime,
        }


# ============================================================
# SANITIZER CLASSIFICATION
# ============================================================

def classify_runtime_error(
    stderr: str,
) -> str | None:

    text = stderr.lower()

    # --------------------------------------------------------
    # Memory errors
    # --------------------------------------------------------

    memory_markers = (
        "addresssanitizer",
        "stack-buffer-overflow",
        "heap-buffer-overflow",
        "global-buffer-overflow",
        "stack-use-after-scope",
        "stack-use-after-return",
        "heap-use-after-free",
        "use-after-free",
        "out-of-bounds",
        "out of bounds",
        "container-overflow",
        "double-free",
        "invalid-free",
    )

    if any(
        marker in text
        for marker in memory_markers
    ):
        return "memory_error"

    # --------------------------------------------------------
    # Integer overflow
    # --------------------------------------------------------

    overflow_markers = (
        "signed integer overflow",
        "unsigned integer overflow",
        "integer overflow",
    )

    if any(
        marker in text
        for marker in overflow_markers
    ):
        return "integer_overflow"

    # --------------------------------------------------------
    # Arithmetic errors
    # --------------------------------------------------------

    arithmetic_markers = (
        "division by zero",
        "integer divide by zero",
        "floating point exception",
        "modulo by zero",
    )

    if any(
        marker in text
        for marker in arithmetic_markers
    ):
        return "arithmetic_error"

    return None


# ============================================================
# CRASH CLASSIFICATION
# ============================================================

def classify_crash(
    input_value: str,
    stderr: str,
) -> tuple[str, str, str]:

    text = stderr.lower()

    # --------------------------------------------------------
    # Invalid vector / container size
    # --------------------------------------------------------

    if (
        "vector" in text
        and (
            "length_error" in text
            or "cannot create std::vector" in text
            or "cannot create" in text
        )
    ):
        return (
            "Invalid Container Size",
            "The program attempted to create a container with an invalid size.",
            "Validate the requested size before constructing the vector or container.",
        )

    # --------------------------------------------------------
    # Allocation failure
    # --------------------------------------------------------

    if (
        "bad_alloc" in text
        or "cannot allocate memory" in text
        or "std::bad_alloc" in text
    ):
        return (
            "Memory Allocation Failure",
            "The program attempted to allocate an invalid or excessive amount of memory.",
            "Validate allocation sizes and reject negative or unreasonably large input values.",
        )

    # --------------------------------------------------------
    # Segmentation fault
    # --------------------------------------------------------

    if (
        "segmentation fault" in text
        or "segfault" in text
        or "sigsegv" in text
    ):
        return (
            "Segmentation Fault",
            "The program accessed an invalid memory address.",
            "Check pointer usage, array indexes, and object lifetimes.",
        )

    # --------------------------------------------------------
    # Abort
    # --------------------------------------------------------

    if (
        "abort" in text
        or "sigabrt" in text
    ):
        return (
            "Runtime Abort",
            "The program terminated itself or was terminated after detecting a fatal runtime condition.",
            "Inspect the operation performed immediately before termination.",
        )

    # --------------------------------------------------------
    # Generic crash
    # --------------------------------------------------------

    return (
        "Crash",
        "The program terminated unexpectedly.",
        "Inspect the runtime failure and validate the affected operation.",
    )


# ============================================================
# FINDING CREATION
# ============================================================

def create_finding(
    finding_type: str,
    input_value: str,
    actual: str = "",
    expected: str = "",
    stderr: str = "",
    runtime: float = 0.0,
) -> dict[str, Any]:

    title = None

    if finding_type == "wrong_answer":

        reason = (
            "The submitted program produced output "
            "different from the reference program."
        )

        fix = (
            "Review the program logic around the "
            "failing input."
        )

        confidence = "HIGH"

    elif finding_type == "integer_overflow":

        reason = (
            "A signed integer calculation exceeded "
            "the representable range of int."
        )

        fix = (
            "Use a wider integer type or explicitly "
            "check the arithmetic range."
        )

        confidence = "HIGH"

    elif finding_type == "memory_error":

        reason = (
            "The program accessed memory outside "
            "a valid object boundary."
        )

        fix = (
            "Check array indexes, pointer usage, "
            "and memory boundaries."
        )

        confidence = "HIGH"

    elif finding_type == "arithmetic_error":

        reason = (
            "The program attempted an invalid "
            "arithmetic operation."
        )

        fix = (
            "Validate arithmetic operands before "
            "performing division or modulo."
        )

        confidence = "HIGH"

    elif finding_type == "timeout":

        reason = (
            "The program exceeded the execution "
            "time limit."
        )

        fix = (
            "Check loop termination conditions and "
            "make sure the loop makes progress."
        )

        confidence = "HIGH"

    elif finding_type == "crash":

        title, reason, fix = classify_crash(
            input_value,
            stderr,
        )

        confidence = "HIGH"

    else:

        reason = (
            "The program failed during execution."
        )

        fix = (
            "Review the program for runtime errors."
        )

        confidence = "MEDIUM"

    result = {
        "input": input_value,
        "type": finding_type,
        "confidence": confidence,
        "affected_inputs": [input_value],
        "runtime": runtime,
        "reason": reason,
        "actual": actual,
        "fix": fix,
        "fix_confidence": confidence,
        "minimal_input": input_value,
    }

    if title:
        result["title"] = title

    if expected != "":
        result["expected"] = expected

    if stderr:
        result["diagnostic"] = stderr[:5000]

    # --------------------------------------------------------
    # Suggested fixes
    # --------------------------------------------------------

    if finding_type == "integer_overflow":

        result["suggested_code"] = (
            "Use long long for calculations that "
            "may exceed the int range, and validate "
            "bounds before arithmetic."
        )

    elif finding_type == "memory_error":

        result["suggested_code"] = (
            "Check that every array index is within "
            "the valid range before accessing memory."
        )

    elif finding_type == "arithmetic_error":

        result["suggested_code"] = (
            "Check the divisor before division or modulo."
        )

    elif finding_type == "timeout":

        result["suggested_code"] = (
            "Check loop termination conditions and "
            "ensure every loop makes progress."
        )

    elif finding_type == "crash":

        result["suggested_code"] = (
            "Validate input-dependent sizes, indexes, "
            "pointers, and runtime operations before use."
        )

    return result


# ============================================================
# MERGE SAME-TYPE FINDINGS
# ============================================================

def merge_findings(
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    merged: dict[str, dict[str, Any]] = {}

    for finding in findings:

        finding_type = finding.get(
            "type",
            "unknown",
        )

        if finding_type not in merged:

            merged[finding_type] = dict(
                finding
            )

            merged[finding_type][
                "affected_inputs"
            ] = list(
                dict.fromkeys(
                    finding.get(
                        "affected_inputs",
                        [],
                    )
                )
            )

            continue

        existing = merged[finding_type]

        affected = existing.setdefault(
            "affected_inputs",
            [],
        )

        for value in finding.get(
            "affected_inputs",
            [],
        ):

            if value not in affected:
                affected.append(value)

    return list(merged.values())


# ============================================================
# SUMMARY
# ============================================================

def calculate_summary(
    findings: list[dict[str, Any]],
    tests_executed: int,
) -> dict[str, int]:

    summary = {
        "passed": tests_executed,
        "memory_errors": 0,
        "integer_overflows": 0,
        "arithmetic_errors": 0,
        "timeouts": 0,
        "crashes": 0,
        "performance_risks": 0,
        "wrong_answers": 0,
    }

    mapping = {
        "memory_error": "memory_errors",
        "integer_overflow": "integer_overflows",
        "arithmetic_error": "arithmetic_errors",
        "timeout": "timeouts",
        "crash": "crashes",
        "performance_risk": "performance_risks",
        "wrong_answer": "wrong_answers",
    }

    failed_inputs: set[str] = set()

    for finding in findings:

        finding_type = finding.get(
            "type",
            "",
        )

        summary_key = mapping.get(
            finding_type
        )

        affected_inputs = finding.get(
            "affected_inputs",
            [],
        )

        if summary_key:

            summary[summary_key] += len(
                affected_inputs
            )

        for value in affected_inputs:

            failed_inputs.add(
                str(value)
            )

    summary["passed"] = max(
        0,
        tests_executed - len(
            failed_inputs
        ),
    )

    return summary


# ============================================================
# TESTING
# ============================================================

def test_programs(
    code: str,
    reference_code: str | None,
    inputs: list[str],
) -> tuple[
    list[dict[str, Any]],
    int,
]:

    findings: list[
        dict[str, Any]
    ] = []

    tests_executed = 0

    with tempfile.TemporaryDirectory() as directory:

        submitted_executable = os.path.join(
            directory,
            "submitted",
        )

        reference_executable = os.path.join(
            directory,
            "reference",
        )

        # ----------------------------------------------------
        # Compile submitted code
        # ----------------------------------------------------

        submitted_ok, submitted_error = compile_cpp(
            code,
            submitted_executable,
            sanitizer=True,
        )

        if not submitted_ok:

            raise RuntimeError(
                "Submitted code failed to compile:\n"
                + submitted_error
            )

        # ----------------------------------------------------
        # Optional reference implementation
        # ----------------------------------------------------

        reference_enabled = bool(
            reference_code
            and reference_code.strip()
        )

        if reference_enabled:

            reference_ok, reference_error = compile_cpp(
                reference_code,
                reference_executable,
                sanitizer=False,
            )

            if not reference_ok:

                raise RuntimeError(
                    "Reference code failed to compile:\n"
                    + reference_error
                )

        # ----------------------------------------------------
        # Execute generated tests
        # ----------------------------------------------------

        for input_value in inputs:

            tests_executed += 1

            # ------------------------------------------------
            # Reference execution
            # ------------------------------------------------

            if reference_enabled:

                expected = run_program(
                    reference_executable,
                    input_value,
                )

            else:

                expected = {
                    "status": "not_available",
                    "returncode": None,
                    "stdout": "",
                    "stderr": "",
                    "runtime": 0.0,
                }

            # ------------------------------------------------
            # Submitted execution
            # ------------------------------------------------

            actual = run_program(
                submitted_executable,
                input_value,
            )

            # ------------------------------------------------
            # Timeout
            # ------------------------------------------------

            if actual["status"] == "timeout":

                findings.append(
                    create_finding(
                        "timeout",
                        input_value,
                        runtime=actual[
                            "runtime"
                        ],
                    )
                )

                continue

            # ------------------------------------------------
            # Sanitizer
            # ------------------------------------------------

            runtime_error = classify_runtime_error(
                actual["stderr"]
            )

            if runtime_error:

                findings.append(
                    create_finding(
                        runtime_error,
                        input_value,
                        actual=actual[
                            "stdout"
                        ],
                        expected=expected.get(
                            "stdout",
                            "",
                        ),
                        stderr=actual[
                            "stderr"
                        ],
                        runtime=actual[
                            "runtime"
                        ],
                    )
                )

                continue

            # ------------------------------------------------
            # Crash
            # ------------------------------------------------

            if actual["returncode"] not in (
                0,
                None,
            ):

                findings.append(
                    create_finding(
                        "crash",
                        input_value,
                        actual=actual[
                            "stdout"
                        ],
                        expected=expected.get(
                            "stdout",
                            "",
                        ),
                        stderr=actual[
                            "stderr"
                        ],
                        runtime=actual[
                            "runtime"
                        ],
                    )
                )

                continue

            # ------------------------------------------------
            # No reference = no differential test
            # ------------------------------------------------

            if not reference_enabled:
                continue

            # ------------------------------------------------
            # Reference timeout
            # ------------------------------------------------

            if expected["status"] == "timeout":
                continue

            actual_output = actual[
                "stdout"
            ].strip()

            expected_output = expected[
                "stdout"
            ].strip()

            # ------------------------------------------------
            # Wrong answer
            # ------------------------------------------------

            if actual_output != expected_output:

                findings.append(
                    create_finding(
                        "wrong_answer",
                        input_value,
                        actual=actual_output,
                        expected=expected_output,
                        runtime=actual[
                            "runtime"
                        ],
                    )
                )

    return (
        merge_findings(findings),
        tests_executed,
    )


# ============================================================
# AI REVIEWER
# ============================================================

def ai_review(
    code: str,
    reference_code: str | None,
    weaknesses: list[dict[str, Any]],
    analysis: dict[str, Any],
) -> dict[str, Any]:

    if not weaknesses:

        return {
            "enabled": False,
            "status": "not_needed",
            "provider": "local",
            "findings": [],
        }

    try:

        result = get_ai_review(
            code=code,
            reference_code=reference_code,
            weaknesses=weaknesses,
            analysis=analysis,
        )

        if not isinstance(
            result,
            dict,
        ):

            return {
                "enabled": False,
                "status": "error",
                "provider": "local",
                "message": (
                    "AI reviewer returned "
                    "an invalid response."
                ),
                "findings": [],
            }

        result.setdefault(
            "enabled",
            True,
        )

        result.setdefault(
            "provider",
            "local",
        )

        result.setdefault(
            "status",
            "completed",
        )

        result.setdefault(
            "findings",
            [],
        )

        return result

    except Exception as exc:

        return {
            "enabled": False,
            "status": "error",
            "provider": "local",
            "message": (
                "Local AI reviewer failed."
            ),
            "error": str(exc),
            "findings": [],
        }


# ============================================================
# MAIN ANALYZE ENDPOINT
# ============================================================

@app.post("/analyze")
def analyze(
    request: AnalyzeRequest,
):

    # --------------------------------------------------------
    # Validate submitted code
    # --------------------------------------------------------

    if not request.code.strip():

        raise HTTPException(
            status_code=400,
            detail="code cannot be empty",
        )

    # --------------------------------------------------------
    # Validate optional reference code
    # --------------------------------------------------------

    if (
        request.reference_code is not None
        and not request.reference_code.strip()
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "reference_code cannot be "
                "an empty string; use null "
                "to omit it."
            ),
        )

    try:

        # ====================================================
        # 1. STATIC ANALYSIS
        # ====================================================

        analysis = analyze_code(
            request.code
        )

        if not isinstance(
            analysis,
            dict,
        ):
            analysis = {}

        # ====================================================
        # 2. TEST GENERATION
        # ====================================================

        generated_inputs = (
            generate_test_inputs(
                request.code,
                analysis,
            )
        )

        if not isinstance(
            generated_inputs,
            list,
        ):

            generated_inputs = []

        # Remove duplicates while
        # preserving order.

        inputs = list(
            dict.fromkeys(
                str(value)
                for value in generated_inputs
            )
        )

        # Hard safety limit.

        inputs = inputs[:MAX_TESTS]

        # Always have at least one test.

        if not inputs:
            inputs = ["0"]

        # ====================================================
        # 3. EXECUTION
        # ====================================================

        weaknesses, tests_executed = (
            test_programs(
                request.code,
                request.reference_code,
                inputs,
            )
        )

        # ====================================================
        # 4. SUMMARY
        # ====================================================

        summary = calculate_summary(
            weaknesses,
            tests_executed,
        )

        # ====================================================
        # 5. AI REVIEW
        # ====================================================

        ai = ai_review(
            code=request.code,
            reference_code=request.reference_code,
            weaknesses=weaknesses,
            analysis=analysis,
        )

        # ====================================================
        # 6. RESPONSE
        # ====================================================

        return {
            "status": (
                "vulnerabilities_found"
                if weaknesses
                else "no_failures_found"
            ),
            "tests_executed": tests_executed,
            "summary": summary,
            "weaknesses": weaknesses,
            "analysis": analysis,
            "ai_review": ai,
        }

    except HTTPException:
        raise

    except RuntimeError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:

        print(
            "ANALYZE ERROR:",
            repr(exc),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Break My Code encountered "
                "an internal error."
            ),
        )