from runner import CppProgram
from generator import generate_tests
from analyzer import analyze_code
import time


# ============================================================
# HELPERS
# ============================================================

def safe_lower(value):
    return (value or "").lower()


def contains_any(text, markers):
    text = safe_lower(text)

    return any(
        marker.lower() in text
        for marker in markers
    )


def parse_int_input(test):
    try:
        return [
            int(x)
            for x in test.split()
        ]
    except (ValueError, TypeError):
        return []


def get_arithmetic_attacks(
    test,
    arithmetic_findings
):
    values = parse_int_input(test)

    attacks = []

    if not values:
        return attacks

    for finding in arithmetic_findings:

        position = finding.get(
            "target_position"
        )

        if position is None:
            continue

        if position < 1:
            continue

        if position > len(values):
            continue

        value = values[position - 1]

        if value == 0:

            attacks.append({
                "finding": finding,
                "position": position,
                "value": value
            })

    return attacks


def get_overflow_attacks(
    test,
    overflow_findings
):
    values = parse_int_input(test)

    if not values:
        return []

    attacks = []

    for finding in overflow_findings:

        variables = finding.get(
            "variables",
            []
        )

        for variable in variables:

            if not isinstance(
                variable,
                str
            ):
                continue

            attacks.append({
                "finding": finding,
                "variable": variable
            })

    return attacks


# ============================================================
# MAIN TESTER
# ============================================================

def test_code(
    user_code,
    reference_code=None
):

    print("================================")
    print("💀 BREAK MY CODE")
    print("================================")

    standalone_mode = (
        reference_code is None
    )

    if standalone_mode:

        print("🧪 Mode: STANDALONE")

        print(
            "No reference program supplied."
        )

        print(
            "Testing for crashes, memory "
            "errors, timeouts, performance "
            "risks and dangerous operations."
        )

    else:

        print("🧪 Mode: DIFFERENTIAL")

        print(
            "Reference program supplied."
        )

        print(
            "Wrong-answer detection enabled."
        )

    print()

    # ========================================================
    # AST ANALYSIS
    # ========================================================

    try:

        analysis = analyze_code(
            user_code
        )

    except Exception as e:

        print(
            "❌ AST ANALYSIS FAILED"
        )

        print(str(e))

        return

    findings = analysis.get(
        "findings",
        []
    )

    inputs = analysis.get(
        "inputs",
        []
    )

    # ========================================================
    # FINDING GROUPS
    # ========================================================

    arithmetic_findings = [
        f
        for f in findings
        if f.get("type")
        in [
            "division",
            "modulo"
        ]
    ]

    overflow_findings = [
        f
        for f in findings
        if f.get("type")
        == "overflow"
    ]

    complexity_findings = [
        f
        for f in findings
        if f.get("type")
        == "complexity"
    ]

    # ========================================================
    # COMPILE USER
    # ========================================================

    print(
        "Compiling user code..."
    )

    user_program = CppProgram(
        user_code
    )

    if user_program.status != "success":

        print(
            "❌ USER CODE FAILED TO COMPILE"
        )

        print(
            user_program.error
        )

        user_program.close()

        return

    print(
        "✓ User code compiled"
    )

    # ========================================================
    # OPTIONAL REFERENCE
    # ========================================================

    reference_program = None

    if not standalone_mode:

        print(
            "Compiling reference code..."
        )

        reference_program = CppProgram(
            reference_code
        )

        if (
            reference_program.status
            != "success"
        ):

            print(
                "❌ REFERENCE CODE FAILED "
                "TO COMPILE"
            )

            print(
                reference_program.error
            )

            user_program.close()
            reference_program.close()

            return

        print(
            "✓ Reference code compiled"
        )

    print()

    # ========================================================
    # PERFORMANCE ANALYSIS
    # ========================================================

    if complexity_findings:

        print(
            "================================"
        )

        print(
            "⚡ PERFORMANCE ANALYSIS"
        )

        print(
            "================================"
        )

        for finding in (
            complexity_findings
        ):

            print(
                f"Detected complexity: "
                f"{finding.get('complexity')}"
            )

            print(
                f"Loop depth: "
                f"{finding.get('loop_depth')}"
            )

            print(
                f"Loop variables: "
                f"{finding.get('variables')}"
            )

            print(
                f"Loop bounds: "
                f"{finding.get('bounds')}"
            )

            print(
                f"Risk: "
                f"{finding.get('risk')}"
            )

            print(
                "--------------------------------"
            )

        print()

    # ========================================================
    # GENERATE TESTS
    # ========================================================

    try:

        tests = generate_tests(
            user_code
        )

    except Exception as e:

        print(
            "❌ TEST GENERATION FAILED"
        )

        print(str(e))

        user_program.close()

        if reference_program:
            reference_program.close()

        return

    print()

    print(
        f"Generated tests: "
        f"{len(tests)}"
    )

    print()

    if not tests:

        print(
            "⚠️ NO TESTS GENERATED"
        )

        print(
            "Cannot declare code safe."
        )

        user_program.close()

        if reference_program:
            reference_program.close()

        return

    # ========================================================
    # COUNTERS
    # ========================================================

    passed = 0
    failed = 0

    wrong_answers = 0
    crashes = 0
    timeouts = 0
    memory_errors = 0
    arithmetic_errors = 0
    integer_overflows = 0
    performance_risks = 0
    reference_failures = 0

    weaknesses = []

    # ========================================================
    # TEST LOOP
    # ========================================================

    for test in tests:

        print(
            f"Testing input: {test}"
        )

        start = time.perf_counter()

        user_result = user_program.run(
            test,
            timeout=2
        )

        runtime = (
            time.perf_counter()
            - start
        )

        status = user_result.get(
            "status"
        )

        stdout = (
            user_result.get(
                "stdout",
                ""
            )
            or ""
        )

        stderr = (
            user_result.get(
                "stderr",
                ""
            )
            or ""
        )

        # ====================================================
        # SANITIZER / RUNTIME EVIDENCE
        # ====================================================

        lower_stderr = (
            stderr.lower()
        )

        memory_evidence = contains_any(
            stderr,
            [
                "addresssanitizer",
                "heap-buffer-overflow",
                "stack-buffer-overflow",
                "global-buffer-overflow",
                "use-after-free",
                "double-free",
                "invalid-free",
                "heap-use-after-free"
            ]
        )

        overflow_evidence = contains_any(
            stderr,
            [
                "undefinedbehaviorsanitizer",
                "signed integer overflow",
                "integer overflow",
                "signed-integer-overflow",
                "unsigned integer overflow",
                "runtime error: signed integer overflow",
                "runtime error: unsigned integer overflow"
            ]
        )

        arithmetic_evidence = contains_any(
            stderr,
            [
                "division by zero",
                "divide by zero",
                "integer division by zero",
                "floating point exception",
                "sigfpe"
            ]
        )

        # ====================================================
        # MEMORY ERROR
        # ====================================================

        if (
            status == "memory_error"
            or memory_evidence
        ):

            failed += 1
            memory_errors += 1

            print(
                "  🚨 MEMORY ERROR"
            )

            weaknesses.append({
                "input": test,
                "type": "memory_error",
                "expected": None,
                "actual": None,
                "runtime": runtime,
                "stderr": stderr
            })

            print()

            continue

        # ====================================================
        # INTEGER OVERFLOW
        # ====================================================

        if (
            overflow_evidence
            and overflow_findings
        ):

            failed += 1
            integer_overflows += 1

            print(
                "  🚨 INTEGER OVERFLOW"
            )

            weaknesses.append({
                "input": test,
                "type": "integer_overflow",
                "expected": None,
                "actual": stdout.strip(),
                "runtime": runtime,
                "stderr": stderr
            })

            print()

            continue

        # ====================================================
        # TIMEOUT
        # ====================================================

        if status == "timeout":

            failed += 1
            timeouts += 1

            if complexity_findings:

                performance_risks += 1

                print(
                    "  💀 TIMEOUT"
                )

                print(
                    "  ⚡ PERFORMANCE RISK"
                )

                weakness_type = (
                    "performance_timeout"
                )

            else:

                print(
                    "  💀 TIMEOUT"
                )

                weakness_type = (
                    "timeout"
                )

            weaknesses.append({
                "input": test,
                "type": weakness_type,
                "expected": None,
                "actual": None,
                "runtime": runtime,
                "stderr": stderr
            })

            print()

            continue

        # ====================================================
        # ARITHMETIC RUNTIME ERROR
        # ====================================================

        if (
            arithmetic_evidence
            and arithmetic_findings
        ):

            failed += 1
            arithmetic_errors += 1

            print(
                "  🚨 ARITHMETIC ERROR"
            )

            weaknesses.append({
                "input": test,
                "type": "arithmetic_error",
                "expected": None,
                "actual": stdout.strip(),
                "runtime": runtime,
                "stderr": stderr
            })

            print()

            continue

        # ====================================================
        # GENERIC RUNTIME ERROR
        # ====================================================

        if status == "runtime_error":

            failed += 1
            crashes += 1

            print(
                "  💥 CRASH"
            )

            weaknesses.append({
                "input": test,
                "type": "runtime_error",
                "expected": None,
                "actual": None,
                "runtime": runtime,
                "stderr": stderr
            })

            print()

            continue

        # ====================================================
        # UNKNOWN STATUS
        # ====================================================

        if status != "success":

            failed += 1

            print(
                f"  ❌ ERROR: {status}"
            )

            weaknesses.append({
                "input": test,
                "type": status,
                "expected": None,
                "actual": None,
                "runtime": runtime,
                "stderr": stderr
            })

            print()

            continue

        # ====================================================
        # AST-GUIDED DIVISION / MODULO ATTACK
        # ====================================================

        arithmetic_attacks = (
            get_arithmetic_attacks(
                test,
                arithmetic_findings
            )
        )

        if (
            standalone_mode
            and arithmetic_attacks
        ):

            failed += 1
            arithmetic_errors += 1

            print(
                "  🚨 DIVISION/MODULO BY ZERO"
            )

            for attack in (
                arithmetic_attacks
            ):

                finding = attack[
                    "finding"
                ]

                operator = (
                    "/"
                    if finding.get("type")
                    == "division"
                    else "%"
                )

                print(
                    f"  Dangerous operation: "
                    f"{finding.get('left')} "
                    f"{operator} "
                    f"{finding.get('right')}"
                )

                print(
                    f"  Input position: "
                    f"{attack['position']}"
                )

                print(
                    f"  Actual value: "
                    f"{attack['value']}"
                )

            weaknesses.append({
                "input": test,
                "type": "arithmetic_error",
                "expected": None,
                "actual": stdout.strip(),
                "runtime": runtime,
                "stderr": stderr
            })

            print()

            continue

        # ====================================================
        # AST-GUIDED OVERFLOW ATTACK
        # ====================================================

        overflow_attacks = (
            get_overflow_attacks(
                test,
                overflow_findings
            )
        )

        # If the analyzer says this input is an
        # overflow attack but the sanitizer did
        # NOT provide evidence, do NOT falsely
        # claim confirmed overflow.
        #
        # We keep it as a successful execution
        # unless sanitizer evidence exists.

        if complexity_findings:

            print(
                f"  ⏱ Runtime: "
                f"{runtime:.4f}s"
            )

        # ====================================================
        # STANDALONE MODE
        # ====================================================

        if standalone_mode:

            passed += 1

            print(
                "  ✓ No failure detected"
            )

            print()

            continue

        # ====================================================
        # REFERENCE MODE
        # ====================================================

        reference_result = (
            reference_program.run(
                test,
                timeout=2
            )
        )

        reference_status = (
            reference_result.get(
                "status"
            )
        )

        reference_stderr = (
            reference_result.get(
                "stderr",
                ""
            )
            or ""
        )

        reference_failed = (
            reference_status
            != "success"
        )

        if contains_any(
            reference_stderr,
            [
                "addresssanitizer",
                "undefinedbehaviorsanitizer",
                "runtime error:",
                "division by zero",
                "divide by zero",
                "floating point exception",
                "sigfpe",
                "segmentation fault"
            ]
        ):

            reference_failed = True

        if reference_failed:

            reference_failures += 1

            print(
                "  ⚠️ REFERENCE FAILED"
            )

            print(
                "  Skipping comparison."
            )

            print()

            continue

        # ====================================================
        # COMPARE OUTPUT
        # ====================================================

        actual = stdout.strip()

        expected = (
            reference_result.get(
                "stdout",
                ""
            )
            or ""
        ).strip()

        if actual == expected:

            passed += 1

            print(
                "  ✓ Passed"
            )

        else:

            failed += 1
            wrong_answers += 1

            print(
                "  💥 WRONG ANSWER"
            )

            print(
                f"  Expected: {expected}"
            )

            print(
                f"  Actual:   {actual}"
            )

            weaknesses.append({
                "input": test,
                "type": "wrong_answer",
                "expected": expected,
                "actual": actual,
                "runtime": runtime,
                "stderr": ""
            })

        print()

    # ========================================================
    # REPORT
    # ========================================================

    print(
        "================================"
    )

    print(
        "📊 TEST REPORT"
    )

    print(
        "================================"
    )

    print(
        f"Mode              : "
        f"{'STANDALONE' if standalone_mode else 'DIFFERENTIAL'}"
    )

    print(
        f"Tests executed    : "
        f"{len(tests)}"
    )

    print(
        f"Passed            : "
        f"{passed}"
    )

    print(
        f"Failed            : "
        f"{failed}"
    )

    print(
        f"Wrong answers     : "
        f"{wrong_answers}"
    )

    print(
        f"Crashes           : "
        f"{crashes}"
    )

    print(
        f"Timeouts          : "
        f"{timeouts}"
    )

    print(
        f"Memory errors     : "
        f"{memory_errors}"
    )

    print(
        f"Arithmetic errors : "
        f"{arithmetic_errors}"
    )

    print(
        f"Integer overflows : "
        f"{integer_overflows}"
    )

    print(
        f"Performance risks : "
        f"{performance_risks}"
    )

    if not standalone_mode:

        print(
            f"Reference failed  : "
            f"{reference_failures}"
        )

    print(
        "================================"
    )

    # ========================================================
    # WEAKNESSES
    # ========================================================

    if weaknesses:

        print()

        print(
            "💀 WEAKNESSES FOUND"
        )

        print(
            "================================"
        )

        for weakness in weaknesses:

            print(
                f"Input : "
                f"{weakness['input']}"
            )

            print(
                f"Type  : "
                f"{weakness['type']}"
            )

            if weakness.get(
                "runtime"
            ) is not None:

                print(
                    f"Runtime : "
                    f"{weakness['runtime']:.4f}s"
                )

            print(
                "--------------------------------"
            )

            # =================================================
            # INTEGER OVERFLOW ROOT CAUSE
            # =================================================

            if weakness["type"] == (
                "integer_overflow"
            ):

                print(
                    "🔎 ROOT-CAUSE ANALYSIS"
                )

                print()

                print(
                    "🚨 INTEGER OVERFLOW"
                )

                print()

                for finding in (
                    overflow_findings
                ):

                    print(
                        f"Operation: "
                        f"{finding.get('left')} "
                        f"{finding.get('operator')} "
                        f"{finding.get('right')}"
                    )

                    print(
                        f"Type: "
                        f"{finding.get('variable_type')}"
                    )

                    print(
                        f"Variables: "
                        f"{finding.get('variables')}"
                    )

                    print(
                        f"Risk: "
                        f"{finding.get('risk')}"
                    )

                    print()

                print(
                    "Evidence: UndefinedBehaviorSanitizer "
                    "reported integer overflow."
                )

                print(
                    "Confidence: HIGH"
                )

            # =================================================
            # MEMORY ROOT CAUSE
            # =================================================

            elif weakness["type"] == (
                "memory_error"
            ):

                print(
                    "🔎 ROOT-CAUSE ANALYSIS"
                )

                print()

                print(
                    "🚨 MEMORY SAFETY VIOLATION"
                )

                array_findings = [
                    f
                    for f in findings
                    if f.get("type")
                    == "array_access"
                ]

                if array_findings:

                    for finding in (
                        array_findings
                    ):

                        print(
                            f"Array access: "
                            f"{finding.get('expression')}"
                        )

                        print(
                            f"Array: "
                            f"{finding.get('array')}"
                        )

                        print(
                            f"Index variable: "
                            f"{finding.get('index_variable')}"
                        )

                        print(
                            f"Array size variable: "
                            f"{finding.get('size_variable')}"
                        )

                        print(
                            f"Risk: "
                            f"{finding.get('risk')}"
                        )

                        print()

                print(
                    "Evidence: AddressSanitizer "
                    "detected an invalid memory access."
                )

                print(
                    "Confidence: HIGH"
                )

            # =================================================
            # ARITHMETIC ROOT CAUSE
            # =================================================

            elif weakness["type"] == (
                "arithmetic_error"
            ):

                print(
                    "🔎 ROOT-CAUSE ANALYSIS"
                )

                print()

                print(
                    "🚨 DANGEROUS "
                    "ARITHMETIC OPERATION"
                )

                for finding in (
                    arithmetic_findings
                ):

                    operator = (
                        "/"
                        if finding.get("type")
                        == "division"
                        else "%"
                    )

                    print(
                        f"Operation: "
                        f"{finding.get('left')} "
                        f"{operator} "
                        f"{finding.get('right')}"
                    )

                    print(
                        f"Input position: "
                        f"{finding.get('target_position')}"
                    )

                    print(
                        f"Risk: "
                        f"{finding.get('risk')}"
                    )

                print()

                print(
                    "Evidence: Break My Code "
                    "generated a zero divisor/"
                    "modulo operand or runtime "
                    "reported arithmetic failure."
                )

                print(
                    "Confidence: HIGH"
                )

            # =================================================
            # PERFORMANCE ROOT CAUSE
            # =================================================

            elif weakness["type"] in [
                "performance_timeout",
                "timeout"
            ]:

                print(
                    "🔎 ROOT-CAUSE ANALYSIS"
                )

                print()

                if complexity_findings:

                    print(
                        "⚡ PERFORMANCE WEAKNESS"
                    )

                    print()

                    for finding in (
                        complexity_findings
                    ):

                        print(
                            f"Detected complexity: "
                            f"{finding.get('complexity')}"
                        )

                        print(
                            f"Loop depth: "
                            f"{finding.get('loop_depth')}"
                        )

                        print(
                            f"Variables: "
                            f"{finding.get('variables')}"
                        )

                    print()

                    print(
                        "Evidence: stress input "
                        "exceeded execution time limit."
                    )

                    print(
                        "Confidence: HIGH"
                    )

                else:

                    print(
                        "Program exceeded "
                        "the execution time limit."
                    )

            # =================================================
            # CRASH
            # =================================================

            elif weakness["type"] == (
                "runtime_error"
            ):

                print(
                    "🔎 ROOT-CAUSE ANALYSIS"
                )

                print()

                print(
                    "💥 PROGRAM CRASHED"
                )

                if weakness.get(
                    "stderr"
                ):

                    print()

                    print(
                        "Runtime evidence:"
                    )

                    print(
                        weakness[
                            "stderr"
                        ]
                    )

            # =================================================
            # WRONG ANSWER
            # =================================================

            elif weakness["type"] == (
                "wrong_answer"
            ):

                print(
                    "🔎 ROOT-CAUSE ANALYSIS"
                )

                print()

                print(
                    "Output differed from "
                    "the reference program."
                )

            print()

            print(
                "================================"
            )

    else:

        print()

        print(
            "🎉 CODE SURVIVED ALL TESTS"
        )

    # ========================================================
    # CLEANUP
    # ========================================================

    user_program.close()

    if reference_program:

        reference_program.close()


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    user_code = """
    #include <iostream>
    using namespace std;

    int main() {

        int n;

        cin >> n;

        cout << n * n;

        return 0;
    }
    """

    test_code(
        user_code
    )