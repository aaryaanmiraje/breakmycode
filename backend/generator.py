from __future__ import annotations

import re
from typing import Any


INT_MIN = -2147483648
INT_MAX = 2147483647


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        value = str(value).strip()

        if value and value not in seen:
            seen.add(value)
            result.append(value)

    return result


# ============================================================
# INPUT DETECTION
# ============================================================

def _extract_variables(code: str) -> list[str]:
    """
    Extract actual scalar variables read directly from stdin.

    Examples:

        cin >> n;
        -> ["n"]

        cin >> a >> b;
        -> ["a", "b"]

        cin >> values[i];
        -> does NOT add "values"

    Array/vector elements are intentionally ignored because
    their index is controlled by the program itself.
    """

    variables: list[str] = []

    # Find every cin statement.
    cin_pattern = r"\bcin\s*((?:>>\s*[^;]+)+)\s*;"

    for match in re.finditer(
        cin_pattern,
        code,
        re.DOTALL,
    ):
        expression = match.group(1)

        # Extract everything following >>
        targets = re.findall(
            r">>\s*([^>\s;]+)",
            expression,
        )

        for target in targets:
            target = target.strip()

            # Ignore array/vector element access:
            #
            # values[i]
            # arr[n]
            # data[index]
            #
            if "[" in target or "]" in target:
                continue

            # Only accept normal identifiers.
            if not re.fullmatch(
                r"[A-Za-z_]\w*",
                target,
            ):
                continue

            if target not in variables:
                variables.append(target)

    return variables

# ============================================================
# ARRAY DETECTION
# ============================================================

def _extract_array_info(
    code: str,
) -> dict[str, dict[str, Any]]:

    arrays: dict[str, dict[str, Any]] = {}

    # Fixed-size arrays:
    #
    # int arr[5];
    # int arr[5] = {...};
    # long long arr[10];
    #
    pattern = (
        r"\b(?:int|long|long\s+long|short|unsigned|float|double|char)"
        r"\s+([A-Za-z_]\w*)"
        r"\s*\[\s*(\d+)\s*\]"
    )

    for match in re.finditer(pattern, code):
        name = match.group(1)
        size = int(match.group(2))

        if size <= 0:
            continue

        arrays[name] = {
            "name": name,
            "size": size,
            "size_variable": None,
            "min_index": 0,
            "max_index": size - 1,
        }

    return arrays


# ============================================================
# BOUNDARY DETECTION
# ============================================================

def _extract_boundaries(
    code: str,
    variables: list[str],
) -> list[dict[str, Any]]:

    findings: list[dict[str, Any]] = []

    pattern = (
        r"\b([A-Za-z_]\w*)\s*"
        r"(==|!=|<=|>=|<|>)\s*"
        r"(-?\d+)"
    )

    for match in re.finditer(pattern, code):
        variable = match.group(1)

        if variable not in variables:
            continue

        operator = match.group(2)
        value = int(match.group(3))
        position = match.start()

        findings.append(
            {
                "type": "boundary",
                "variable": variable,
                "operator": operator,
                "value": value,
                "target_position": variables.index(variable) + 1,
                "location": {
                    "line": code.count("\n", 0, position) + 1,
                    "column": position
                    - code.rfind("\n", 0, position),
                },
                "risk": "Possible boundary condition",
            }
        )

    return findings


# ============================================================
# LOOP DETECTION
# ============================================================

def _extract_loops(
    code: str,
    variables: list[str],
) -> list[dict[str, Any]]:

    findings: list[dict[str, Any]] = []

    pattern = r"\b(while|for)\s*\((.*?)\)\s*\{"

    for match in re.finditer(
        pattern,
        code,
        re.DOTALL,
    ):
        loop_type = match.group(1)
        condition = match.group(2).strip()

        variable = None

        # Prefer actual input variables when identifying
        # loop-controlled user input.
        for name in variables:
            if re.search(
                rf"\b{re.escape(name)}\b",
                condition,
            ):
                variable = name
                break

        # If this is a local loop variable such as i,
        # still inspect it for infinite-loop risk.
        if variable is None:
            variable_match = re.search(
                r"\b([A-Za-z_]\w*)\b",
                condition,
            )

            if variable_match:
                variable = variable_match.group(1)

        if variable is None:
            continue

        start = match.end()
        depth = 1
        index = start

        while index < len(code) and depth:
            if code[index] == "{":
                depth += 1
            elif code[index] == "}":
                depth -= 1

            index += 1

        body = code[start:index - 1]

        modified = bool(
            re.search(
                rf"\b{re.escape(variable)}\s*"
                r"(\+\+|--|\+=|-=|=)",
                body,
            )
        )

        if loop_type == "while" and not modified:
            position = match.start()

            findings.append(
                {
                    "type": "loop",
                    "loop": (
                        f"while ({condition}) {{\n"
                        f"    {body.strip()}\n"
                        f"}}"
                    ),
                    "variable": variable,
                    "variable_changes": False,
                    "infinite_loop_risk": True,
                    "location": {
                        "line": code.count(
                            "\n",
                            0,
                            position,
                        ) + 1,
                        "column": position
                        - code.rfind(
                            "\n",
                            0,
                            position,
                        ),
                    },
                    "risk": (
                        "Loop control variable "
                        "is never modified"
                    ),
                }
            )

    return findings


# ============================================================
# ARRAY ACCESS DETECTION
# ============================================================

def _extract_array_accesses(
    code: str,
    arrays: dict[str, dict[str, Any]],
    variables: list[str],
) -> list[dict[str, Any]]:

    findings: list[dict[str, Any]] = []

    for array_name, info in arrays.items():

        pattern = (
            rf"\b{re.escape(array_name)}"
            r"\s*\[\s*([A-Za-z_]\w*)\s*\]"
        )

        for match in re.finditer(
            pattern,
            code,
        ):
            index_variable = match.group(1)

            # The index must actually be an input
            # variable for generated input testing.
            if index_variable not in variables:
                continue

            position = match.start()

            findings.append(
                {
                    "type": "array_access",
                    "expression": (
                        f"{array_name}"
                        f"[{index_variable}]"
                    ),
                    "array": array_name,
                    "index_variable": index_variable,
                    "index_position": (
                        variables.index(index_variable) + 1
                    ),
                    "array_size": info["size"],
                    "size_variable": None,
                    "size_position": None,
                    "min_index": 0,
                    "max_index": info["size"] - 1,
                    "location": {
                        "line": code.count(
                            "\n",
                            0,
                            position,
                        ) + 1,
                        "column": position
                        - code.rfind(
                            "\n",
                            0,
                            position,
                        ),
                    },
                    "risk": (
                        "Possible out-of-bounds access"
                    ),
                }
            )

    return findings


# ============================================================
# DIVISION / MODULO DETECTION
# ============================================================

def _extract_divisions(
    code: str,
    variables: list[str],
) -> list[dict[str, Any]]:

    findings: list[dict[str, Any]] = []

    pattern = (
        r"([A-Za-z_]\w*|-?\d+)"
        r"\s*(/|%)\s*"
        r"([A-Za-z_]\w*|-?\d+)"
    )

    for match in re.finditer(
        pattern,
        code,
    ):
        left = match.group(1)
        operator = match.group(2)
        right = match.group(3)

        if right not in variables:
            continue

        position = match.start()

        findings.append(
            {
                "type": "division",
                "left": left,
                "right": right,
                "operator": operator,
                "target": right,
                "target_position": (
                    variables.index(right) + 1
                ),
                "location": {
                    "line": code.count(
                        "\n",
                        0,
                        position,
                    ) + 1,
                    "column": position
                    - code.rfind(
                        "\n",
                        0,
                        position,
                    ),
                },
                "risk": "Possible division by zero",
            }
        )

    return findings


# ============================================================
# ARITHMETIC / OVERFLOW DETECTION
# ============================================================

def _extract_arithmetic(
    code: str,
) -> list[dict[str, Any]]:

    findings: list[dict[str, Any]] = []

    pattern = (
        r"\b([A-Za-z_]\w*|-?\d+)\s*"
        r"(\+|-|\*)\s*"
        r"([A-Za-z_]\w*|-?\d+)"
    )

    for match in re.finditer(
        pattern,
        code,
    ):
        left = match.group(1)
        operator = match.group(2)
        right = match.group(3)

        variables: list[str] = []

        if re.match(
            r"^[A-Za-z_]\w*$",
            left,
        ):
            variables.append(left)

        if re.match(
            r"^[A-Za-z_]\w*$",
            right,
        ):
            variables.append(right)

        if not variables:
            continue

        position = match.start()

        findings.append(
            {
                "type": "overflow",
                "operator": operator,
                "left": left,
                "right": right,
                "variables": variables,
                "variable_type": "int",
                "location": {
                    "line": code.count(
                        "\n",
                        0,
                        position,
                    ) + 1,
                    "column": position
                    - code.rfind(
                        "\n",
                        0,
                        position,
                    ),
                },
                "risk": (
                    "Possible signed integer overflow"
                ),
            }
        )

    return findings


# ============================================================
# STATIC ANALYSIS
# ============================================================

def analyze_code(
    code: str,
) -> dict[str, Any]:

    variables = _extract_variables(code)
    arrays = _extract_array_info(code)

    findings: list[dict[str, Any]] = []

    findings.extend(
        _extract_boundaries(
            code,
            variables,
        )
    )

    findings.extend(
        _extract_loops(
            code,
            variables,
        )
    )

    findings.extend(
        _extract_array_accesses(
            code,
            arrays,
            variables,
        )
    )

    findings.extend(
        _extract_arithmetic(code)
    )

    findings.extend(
        _extract_divisions(
            code,
            variables,
        )
    )

    return {
        "inputs": variables,
        "arrays": arrays,
        "findings": findings,
    }


# ============================================================
# VALUE GENERATION
# ============================================================

def _values_for_variable(
    variable: str,
    analysis: dict[str, Any],
) -> list[int]:

    # Safe baseline values.
    values = [
        0,
        1,
        -1,
        2,
        -2,
        5,
        10,
        100,
        -100,
        1000,
        -1000,
    ]

    for finding in analysis.get(
        "findings",
        [],
    ):

        # Boundary testing
        if finding.get("variable") == variable:

            if "value" in finding:
                value = int(
                    finding["value"]
                )

                values.extend(
                    [
                        value - 1,
                        value,
                        value + 1,
                    ]
                )

        # Array index testing
        if finding.get(
            "index_variable"
        ) == variable:

            maximum = int(
                finding.get(
                    "max_index",
                    4,
                )
            )

            values.extend(
                [
                    -1,
                    0,
                    1,
                    max(0, maximum - 1),
                    maximum,
                    maximum + 1,
                ]
            )

    return list(
        dict.fromkeys(
            values
        )
    )


# ============================================================
# TEST GENERATION
# ============================================================

def generate_test_inputs(
    code: str,
    analysis: dict[str, Any],
) -> list[str]:

    variables = analysis.get(
        "inputs",
        [],
    )

    # No stdin input.
    if not variables:
        return [""]

    # --------------------------------------------------------
    # SINGLE INPUT
    # --------------------------------------------------------

    if len(variables) == 1:

        values = _values_for_variable(
            variables[0],
            analysis,
        )

        return _unique(
            [
                str(value)
                for value in values
            ]
        )

    # --------------------------------------------------------
    # MULTIPLE INPUTS
    # --------------------------------------------------------

    tests: list[str] = []

    # Safe baseline.
    safe_values = [
        0,
        1,
        -1,
        2,
        -2,
        5,
        10,
        100,
        -100,
    ]

    # Same value for every input.
    for value in safe_values:

        tests.append(
            " ".join(
                str(value)
                for _ in variables
            )
        )

    # --------------------------------------------------------
    # Pairwise edge cases
    # --------------------------------------------------------

    if len(variables) >= 2:

        tests.extend(
            [
                "0 1",
                "1 0",
                "1 -1",
                "-1 1",
                "0 -1",
                "-1 0",
                "2 1",
                "1 2",
                "10 1",
                "1 10",
                "-10 1",
                "1 -10",
            ]
        )

    # --------------------------------------------------------
    # Overflow-focused tests
    # Only use these when arithmetic was detected.
    # --------------------------------------------------------

    has_overflow = any(
        finding.get("type") == "overflow"
        for finding in analysis.get(
            "findings",
            [],
        )
    )

    if has_overflow:

        if len(variables) == 2:
            tests.extend(
                [
                    "46341 46341",
                    "50000 50000",
                    "-50000 50000",
                    "2000000000 2",
                    "-2000000000 2",
                ]
            )

        else:
            # Use moderate values for larger
            # input counts to avoid pathological
            # calculations.
            tests.extend(
                [
                    " ".join(
                        "46341"
                        for _ in variables
                    ),
                    " ".join(
                        "50000"
                        for _ in variables
                    ),
                ]
            )

    # --------------------------------------------------------
    # Division-by-zero tests
    # --------------------------------------------------------

    division_findings = [
        finding
        for finding in analysis.get(
            "findings",
            [],
        )
        if finding.get("type") == "division"
    ]

    for finding in division_findings:

        target_position = finding.get(
            "target_position"
        )

        if not target_position:
            continue

        position = int(
            target_position
        ) - 1

        if position < 0:
            continue

        values = [
            1
            for _ in variables
        ]

        if position < len(values):
            values[position] = 0

        tests.append(
            " ".join(
                str(value)
                for value in values
            )
        )

    # --------------------------------------------------------
    # Array boundary tests
    # --------------------------------------------------------

    array_findings = [
        finding
        for finding in analysis.get(
            "findings",
            [],
        )
        if finding.get(
            "type"
        ) == "array_access"
    ]

    for finding in array_findings:

        position = finding.get(
            "index_position"
        )

        if not position:
            continue

        position = int(position) - 1

        maximum = int(
            finding.get(
                "max_index",
                4,
            )
        )

        # Keep every other input safe.
        values = [
            1
            for _ in variables
        ]

        if 0 <= position < len(values):

            # Test:
            # -1
            # valid maximum
            # maximum + 1
            for index_value in [
                -1,
                maximum,
                maximum + 1,
            ]:

                test_values = values.copy()
                test_values[position] = index_value

                tests.append(
                    " ".join(
                        str(value)
                        for value in test_values
                    )
                )

    return _unique(tests)


# ============================================================
# PUBLIC ENTRY POINT
# ============================================================

def generate_tests(
    code: str,
) -> dict[str, Any]:

    analysis = analyze_code(code)

    inputs = generate_test_inputs(
        code,
        analysis,
    )

    return {
        "security": inputs,
        "correctness": inputs,
        "analysis": analysis,
    }