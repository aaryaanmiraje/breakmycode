from runner import run_cpp


# ============================================================
# FAILURE CLASSIFICATION
# ============================================================

def classify_failure(stderr, status):

    text = (stderr or "").lower()

    memory_markers = [
        "addresssanitizer",
        "heap-buffer-overflow",
        "stack-buffer-overflow",
        "global-buffer-overflow",
        "use-after-free",
        "heap-use-after-free",
        "double-free",
        "invalid-free",
    ]

    if any(x in text for x in memory_markers):
        return "memory_error"

    arithmetic_markers = [
        "division by zero",
        "divide by zero",
        "integer division by zero",
        "floating point exception",
        "sigfpe",
    ]

    if any(x in text for x in arithmetic_markers):
        return "arithmetic_error"

    overflow_markers = [
        "signed integer overflow",
        "unsigned integer overflow",
        "integer overflow",
    ]

    if any(x in text for x in overflow_markers):
        return "integer_overflow"

    if status == "timeout":
        return "timeout"

    if status == "runtime_error":
        return "runtime_error"

    return None


# ============================================================
# CHECK SAME FAILURE
# ============================================================

def still_fails(
    code,
    test_input,
    vulnerability_type
):

    result = run_cpp(
        code,
        test_input
    )

    detected = classify_failure(
        result.get("stderr", ""),
        result.get("status")
    )

    return detected == vulnerability_type


# ============================================================
# CHECK WRONG ANSWER
# ============================================================

def still_wrong(
    user_code,
    reference_code,
    test_input
):

    user_result = run_cpp(
        user_code,
        test_input
    )

    reference_result = run_cpp(
        reference_code,
        test_input
    )

    if user_result.get("status") != "success":
        return False

    if reference_result.get("status") != "success":
        return False

    user_output = (
        user_result.get("stdout", "")
        or ""
    ).strip()

    expected_output = (
        reference_result.get("stdout", "")
        or ""
    ).strip()

    return user_output != expected_output


# ============================================================
# PARSE INTEGER INPUT
# ============================================================

def parse_integer_input(
    failing_input
):

    try:

        return [
            int(x)
            for x in failing_input.split()
        ]

    except ValueError:

        return None


# ============================================================
# FORMAT INPUT
# ============================================================

def format_input(
    values
):

    return " ".join(
        map(str, values)
    )


# ============================================================
# TEST INTEGER VALUE
# ============================================================

def test_integer_value(
    code,
    values,
    index,
    candidate,
    vulnerability_type
):

    trial = values.copy()

    trial[index] = candidate

    test_input = format_input(
        trial
    )

    print(
        f"      Trying: {test_input}"
    )

    if still_fails(
        code,
        test_input,
        vulnerability_type
    ):

        print(
            f"      ✓ Still failing: "
            f"{test_input}"
        )

        return True

    return False


# ============================================================
# MINIMIZE INTEGER OVERFLOW
# ============================================================

def minimize_overflow(
    code,
    failing_input
):

    values = parse_integer_input(
        failing_input
    )

    if values is None:
        return failing_input

    current = values.copy()

    # --------------------------------------------------------
    # Process every integer input position
    # --------------------------------------------------------

    for index, original in enumerate(values):

        # ----------------------------------------------------
        # Positive overflow
        # ----------------------------------------------------

        if original > 0:

            low = 0
            high = original

            # ------------------------------------------------
            # Find smallest positive failing value
            # ------------------------------------------------

            while low < high:

                mid = (
                    low + high
                ) // 2

                if mid == 0:
                    mid = 1

                print(
                    f"      Trying: "
                    f"{format_input(current[:index] + [mid] + current[index+1:])}"
                )

                trial = current.copy()

                trial[index] = mid

                trial_input = format_input(
                    trial
                )

                if still_fails(
                    code,
                    trial_input,
                    "integer_overflow"
                ):

                    high = mid

                else:

                    low = mid + 1

            # ------------------------------------------------
            # Verify boundary
            # ------------------------------------------------

            candidate = low

            trial = current.copy()

            trial[index] = candidate

            if still_fails(
                code,
                format_input(trial),
                "integer_overflow"
            ):

                current[index] = candidate

        # ----------------------------------------------------
        # Negative overflow
        # ----------------------------------------------------

        elif original < 0:

            # Work with absolute magnitude.
            magnitude = abs(original)

            low = 0
            high = magnitude

            while low < high:

                mid = (
                    low + high
                ) // 2

                if mid == 0:
                    mid = 1

                candidate = -mid

                trial = current.copy()

                trial[index] = candidate

                trial_input = format_input(
                    trial
                )

                print(
                    f"      Trying: "
                    f"{trial_input}"
                )

                if still_fails(
                    code,
                    trial_input,
                    "integer_overflow"
                ):

                    high = mid

                else:

                    low = mid + 1

            candidate = -low

            trial = current.copy()

            trial[index] = candidate

            if still_fails(
                code,
                format_input(trial),
                "integer_overflow"
            ):

                current[index] = candidate

    # --------------------------------------------------------
    # Prefer positive counterexample when both signs
    # are equally minimal.
    # --------------------------------------------------------

    if len(current) == 1:

        positive = abs(
            current[0]
        )

        negative = -abs(
            current[0]
        )

        positive_input = str(
            positive
        )

        negative_input = str(
            negative
        )

        positive_fails = still_fails(
            code,
            positive_input,
            "integer_overflow"
        )

        negative_fails = still_fails(
            code,
            negative_input,
            "integer_overflow"
        )

        if positive_fails:

            return positive_input

        if negative_fails:

            return negative_input

    return format_input(
        current
    )


# ============================================================
# MINIMIZE GENERAL FAILURE
# ============================================================

def minimize_general_failure(
    code,
    failing_input,
    vulnerability_type
):

    values = parse_integer_input(
        failing_input
    )

    if values is None:
        return failing_input

    current = values.copy()

    # --------------------------------------------------------
    # Try zero, one and minus one.
    # --------------------------------------------------------

    for index, original in enumerate(
        values
    ):

        candidates = [
            0,
            1,
            -1
        ]

        # Prefer smaller absolute values.
        candidates.sort(
            key=lambda x: (
                abs(x),
                x < 0
            )
        )

        for candidate in candidates:

            if candidate == original:
                continue

            trial = current.copy()

            trial[index] = candidate

            trial_input = format_input(
                trial
            )

            print(
                f"      Trying: "
                f"{trial_input}"
            )

            if still_fails(
                code,
                trial_input,
                vulnerability_type
            ):

                current = trial

                print(
                    f"      ✓ Still failing: "
                    f"{trial_input}"
                )

                break

    return format_input(
        current
    )


# ============================================================
# MINIMIZE WRONG ANSWER
# ============================================================

def minimize_wrong_answer(
    user_code,
    reference_code,
    failing_input
):

    values = parse_integer_input(
        failing_input
    )

    if values is None:
        return failing_input

    current = values.copy()

    for index, original in enumerate(
        values
    ):

        candidates = [
            0,
            1,
            -1,
            original // 2,
            original // 4
        ]

        candidates = list(
            dict.fromkeys(
                candidates
            )
        )

        candidates.sort(
            key=lambda x: (
                abs(x),
                x < 0
            )
        )

        for candidate in candidates:

            if candidate == original:
                continue

            trial = current.copy()

            trial[index] = candidate

            trial_input = format_input(
                trial
            )

            print(
                f"      Trying: "
                f"{trial_input}"
            )

            if still_wrong(
                user_code,
                reference_code,
                trial_input
            ):

                current = trial

                print(
                    f"      ✓ Still wrong: "
                    f"{trial_input}"
                )

                break

    return format_input(
        current
    )


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def minimize(
    code,
    failing_input,
    vulnerability_type,
    reference_code=None
):

    # --------------------------------------------------------
    # Integer overflow gets special treatment.
    # --------------------------------------------------------

    if vulnerability_type == "integer_overflow":

        return minimize_overflow(
            code,
            failing_input
        )

    # --------------------------------------------------------
    # Wrong answer
    # --------------------------------------------------------

    if vulnerability_type == "wrong_answer":

        if not reference_code:

            return failing_input

        return minimize_wrong_answer(
            code,
            reference_code,
            failing_input
        )

    # --------------------------------------------------------
    # Everything else
    # --------------------------------------------------------

    return minimize_general_failure(
        code,
        failing_input,
        vulnerability_type
    )


# ============================================================
# MANUAL TEST
# ============================================================

if __name__ == "__main__":

    code = """
#include <iostream>
using namespace std;

int main() {

    int n;

    cin >> n;

    int result = n * n;

    cout << result;

    return 0;
}
"""

    original_input = "50000"

    result = minimize(
        code,
        original_input,
        "integer_overflow"
    )

    print()
    print(
        "Original input :",
        original_input
    )

    print(
        "Minimal input  :",
        result
    )