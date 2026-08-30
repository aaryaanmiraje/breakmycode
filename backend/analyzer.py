from tree_sitter import Language, Parser
import tree_sitter_cpp


CPP_LANGUAGE = Language(tree_sitter_cpp.language())
parser = Parser(CPP_LANGUAGE)


# ============================================================
# HELPERS
# ============================================================

def get_node_text(code, node):
    return code[node.start_byte:node.end_byte]


def node_location(node):
    """
    Tree-sitter rows are zero-based.
    Convert them to human-friendly 1-based line/column.
    """
    return {
        "line": node.start_point[0] + 1,
        "column": node.start_point[1] + 1
    }


def analyze_code(code):

    tree = parser.parse(
        code.encode("utf-8")
    )

    root = tree.root_node

    input_variables = []
    findings = []
    arrays = {}
    variable_types = {}

    # ========================================================
    # TEXT
    # ========================================================

    def get_text(node):
        return get_node_text(
            code,
            node
        )

    # ========================================================
    # INPUT VARIABLES
    # ========================================================

    def collect_input_variables(node):

        text = get_text(node)

        if node.type == "binary_expression":

            if "cin" in text and ">>" in text:

                def find_input_identifiers(child):

                    if child.type == "identifier":

                        name = get_text(
                            child
                        )

                        if name != "cin":

                            input_variables.append(
                                name
                            )

                    for subchild in child.children:

                        find_input_identifiers(
                            subchild
                        )

                find_input_identifiers(
                    node
                )

        for child in node.children:

            collect_input_variables(
                child
            )

    # ========================================================
    # VARIABLE TYPES
    # ========================================================

    def collect_variable_types(node):

        if node.type == "declaration":

            declaration_text = get_text(
                node
            )

            detected_type = None

            if "unsigned long long" in declaration_text:

                detected_type = (
                    "unsigned long long"
                )

            elif "long long" in declaration_text:

                detected_type = (
                    "long long"
                )

            elif "unsigned int" in declaration_text:

                detected_type = (
                    "unsigned int"
                )

            elif "int" in declaration_text:

                detected_type = "int"

            elif "long" in declaration_text:

                detected_type = "long"

            elif "short" in declaration_text:

                detected_type = "short"

            if detected_type:

                for child in node.children:

                    if child.type in [
                        "init_declarator",
                        "identifier"
                    ]:

                        text = get_text(
                            child
                        )

                        if text:

                            name = (
                                text
                                .split("=")[0]
                                .strip()
                            )

                            name = (
                                name
                                .replace("*", "")
                                .replace("&", "")
                                .strip()
                            )

                            if name.isidentifier():

                                variable_types[
                                    name
                                ] = detected_type

        for child in node.children:

            collect_variable_types(
                child
            )

    # ========================================================
    # ARRAY DECLARATIONS
    # ========================================================

    def collect_arrays(node):

        if node.type == "array_declarator":

            array_name = None
            size = None
            size_variable = None

            for child in node.children:

                if child.type == "identifier":

                    array_name = get_text(
                        child
                    )

                    break

            for child in node.children:

                if child.type == "number_literal":

                    try:

                        size = int(
                            get_text(child)
                        )

                    except ValueError:

                        pass

                elif child.type == "identifier":

                    possible_variable = get_text(
                        child
                    )

                    if (
                        possible_variable
                        != array_name
                        and
                        possible_variable
                        in input_variables
                    ):

                        size_variable = (
                            possible_variable
                        )

            if array_name is not None:

                arrays[
                    array_name
                ] = {
                    "name": array_name,
                    "size": size,
                    "size_variable": size_variable,
                    "min_index": 0,
                    "max_index": (
                        size - 1
                        if size is not None
                        else None
                    )
                }

        for child in node.children:

            collect_arrays(
                child
            )

    # ========================================================
    # VARIABLE MODIFICATION
    # ========================================================

    def variable_changes(
        node,
        variable
    ):

        text = get_text(
            node
        )

        if (
            "++" in text
            or "--" in text
        ):

            if variable in text:

                return True

        for operator in [
            "+=",
            "-=",
            "*=",
            "/=",
            "%="
        ]:

            if (
                variable in text
                and operator in text
            ):

                return True

        if node.type == "assignment_expression":

            if text.startswith(
                variable
            ):

                if "=" in text:

                    return True

        for child in node.children:

            if variable_changes(
                child,
                variable
            ):

                return True

        return False

    # ========================================================
    # FOR LOOP INFO
    # ========================================================

    def get_for_loop_info(node):

        variable = None
        condition = ""
        bound_variable = None
        direction = None

        text = get_text(
            node
        )

        if node.type == "for_statement":

            for child in node.children:

                child_text = get_text(
                    child
                )

                if (
                    "int " in child_text
                    or "long " in child_text
                    or "size_t " in child_text
                ):

                    words = (
                        child_text
                        .replace("=", " ")
                        .replace(";", " ")
                        .split()
                    )

                    for index, word in enumerate(
                        words
                    ):

                        if word in [
                            "int",
                            "long",
                            "size_t"
                        ]:

                            if (
                                index + 1
                                < len(words)
                            ):

                                candidate = (
                                    words[
                                        index + 1
                                    ]
                                )

                                if candidate.isidentifier():

                                    variable = candidate

                                    break

                if child.type == "binary_expression":

                    condition = get_text(
                        child
                    )

                    if len(
                        child.children
                    ) >= 3:

                        right = get_text(
                            child.children[2]
                        )

                        if (
                            right
                            in input_variables
                        ):

                            bound_variable = right

                        elif right.isidentifier():

                            bound_variable = right

                if "++" in child_text:

                    direction = "increasing"

                elif "--" in child_text:

                    direction = "decreasing"

        return {
            "variable": variable,
            "condition": condition,
            "bound_variable": bound_variable,
            "direction": direction,
            "text": text
        }

    # ========================================================
    # COMPLEXITY
    # ========================================================

    def analyze_complexity(
        node,
        loop_stack=None
    ):

        if loop_stack is None:

            loop_stack = []

        if node.type == "for_statement":

            info = get_for_loop_info(
                node
            )

            current_stack = (
                loop_stack + [info]
            )

            if len(current_stack) >= 2:

                variables = []
                bounds = []

                for loop in current_stack:

                    if loop["variable"]:

                        variables.append(
                            loop["variable"]
                        )

                    if loop["bound_variable"]:

                        bounds.append(
                            loop["bound_variable"]
                        )

                depth = len(
                    current_stack
                )

                if depth == 2:

                    complexity = "O(n²)"

                elif depth == 3:

                    complexity = "O(n³)"

                else:

                    complexity = (
                        f"O(n^{depth})"
                    )

                findings.append({
                    "type": "complexity",
                    "complexity": complexity,
                    "loop_depth": depth,
                    "variables": variables,
                    "bounds": bounds,
                    "loop": get_text(node),
                    "risk": (
                        "Nested loops may cause "
                        "high computational cost"
                    )
                })

            for child in node.children:

                analyze_complexity(
                    child,
                    current_stack
                )

            return

        if node.type == "while_statement":

            current_stack = (
                loop_stack
                + [{
                    "variable": None,
                    "condition": get_text(node),
                    "bound_variable": None,
                    "direction": None,
                    "text": get_text(node)
                }]
            )

            if len(current_stack) >= 2:

                depth = len(
                    current_stack
                )

                if depth == 2:

                    complexity = "O(n²)"

                elif depth == 3:

                    complexity = "O(n³)"

                else:

                    complexity = (
                        f"O(n^{depth})"
                    )

                findings.append({
                    "type": "complexity",
                    "complexity": complexity,
                    "loop_depth": depth,
                    "variables": [],
                    "bounds": [],
                    "loop": get_text(node),
                    "risk": (
                        "Nested loops may cause "
                        "high computational cost"
                    )
                })

            for child in node.children:

                analyze_complexity(
                    child,
                    current_stack
                )

            return

        for child in node.children:

            analyze_complexity(
                child,
                loop_stack
            )

    # ========================================================
    # ARITHMETIC / OVERFLOW
    # ========================================================

    def analyze_arithmetic(node):

        if node.type == "binary_expression":

            if len(
                node.children
            ) >= 3:

                left_node = (
                    node.children[0]
                )

                operator_node = (
                    node.children[1]
                )

                right_node = (
                    node.children[2]
                )

                left = get_text(
                    left_node
                )

                operator = get_text(
                    operator_node
                )

                right = get_text(
                    right_node
                )

                # ------------------------------------------------
                # DIVISION
                # ------------------------------------------------

                if operator == "/":

                    position = None

                    if right in input_variables:

                        position = (
                            input_variables.index(
                                right
                            ) + 1
                        )

                    findings.append({
                        "type": "division",
                        "left": left,
                        "right": right,
                        "target": right,
                        "target_position": position,
                        "location": node_location(
                            node
                        ),
                        "risk": (
                            "Possible division "
                            "by zero"
                        )
                    })

                # ------------------------------------------------
                # MODULO
                # ------------------------------------------------

                elif operator == "%":

                    position = None

                    if right in input_variables:

                        position = (
                            input_variables.index(
                                right
                            ) + 1
                        )

                    findings.append({
                        "type": "modulo",
                        "left": left,
                        "right": right,
                        "target": right,
                        "target_position": position,
                        "location": node_location(
                            node
                        ),
                        "risk": (
                            "Possible modulo "
                            "by zero"
                        )
                    })

                # ------------------------------------------------
                # OVERFLOW
                # ------------------------------------------------

                elif operator in [
                    "+",
                    "-",
                    "*"
                ]:

                    controlled_variables = []

                    if left in input_variables:

                        controlled_variables.append(
                            left
                        )

                    if right in input_variables:

                        controlled_variables.append(
                            right
                        )

                    if (
                        left in input_variables
                        or right in input_variables
                    ):

                        involved_types = []

                        for variable in (
                            controlled_variables
                        ):

                            variable_type = (
                                variable_types.get(
                                    variable
                                )
                            )

                            if variable_type:

                                involved_types.append(
                                    variable_type
                                )

                        if not involved_types:

                            involved_types = [
                                "int"
                            ]

                        for variable_type in (
                            involved_types
                        ):

                            if variable_type in [
                                "int",
                                "short",
                                "long"
                            ]:

                                findings.append({
                                    "type": "overflow",
                                    "operator": operator,
                                    "left": left,
                                    "right": right,
                                    "variables": (
                                        controlled_variables
                                    ),
                                    "variable_type": (
                                        variable_type
                                    ),
                                    "location": node_location(
                                        node
                                    ),
                                    "risk": (
                                        "Possible signed "
                                        "integer overflow"
                                    )
                                })

                            elif variable_type == (
                                "unsigned int"
                            ):

                                findings.append({
                                    "type": "overflow",
                                    "operator": operator,
                                    "left": left,
                                    "right": right,
                                    "variables": (
                                        controlled_variables
                                    ),
                                    "variable_type": (
                                        variable_type
                                    ),
                                    "location": node_location(
                                        node
                                    ),
                                    "risk": (
                                        "Possible unsigned "
                                        "integer wraparound"
                                    )
                                })

        for child in node.children:

            analyze_arithmetic(
                child
            )

    # ========================================================
    # OTHER OPERATIONS
    # ========================================================

    def analyze_operations(node):

        # ====================================================
        # BOUNDARIES
        # ====================================================

        if node.type == "binary_expression":

            if len(
                node.children
            ) >= 3:

                left = get_text(
                    node.children[0]
                )

                operator = get_text(
                    node.children[1]
                )

                right = get_text(
                    node.children[2]
                )

                if operator in [
                    ">",
                    "<",
                    ">=",
                    "<=",
                    "==",
                    "!="
                ]:

                    try:

                        number = int(
                            right
                        )

                        position = None

                        if left in input_variables:

                            position = (
                                input_variables.index(
                                    left
                                ) + 1
                            )

                        findings.append({
                            "type": "boundary",
                            "variable": left,
                            "operator": operator,
                            "value": number,
                            "target_position": position,
                            "location": node_location(
                                node
                            ),
                            "risk": (
                                "Possible boundary "
                                "condition"
                            )
                        })

                    except ValueError:

                        pass

        # ====================================================
        # WHILE
        # ====================================================

        if node.type == "while_statement":

            loop_text = get_text(
                node
            )

            condition_text = ""

            for child in node.children:

                if (
                    child.type
                    == "parenthesized_expression"
                ):

                    condition_text = get_text(
                        child
                    )

                    break

            if not condition_text:

                condition_text = (
                    loop_text.split("{")[0]
                )

            controlling_variable = None

            for variable in input_variables:

                if variable in condition_text:

                    controlling_variable = variable

                    break

            changes = False

            if controlling_variable:

                for child in node.children:

                    if (
                        child.type
                        == "compound_statement"
                    ):

                        changes = variable_changes(
                            child,
                            controlling_variable
                        )

            infinite_risk = (
                controlling_variable is not None
                and not changes
            )

            findings.append({
                "type": "loop",
                "loop": loop_text,
                "variable": controlling_variable,
                "variable_changes": changes,
                "infinite_loop_risk": infinite_risk,
                "location": node_location(
                    node
                ),
                "risk": (
                    "Loop control variable "
                    "is never modified"
                    if infinite_risk
                    else
                    "Loop control variable "
                    "is modified"
                )
            })

        # ====================================================
        # FOR
        # ====================================================

        if node.type == "for_statement":

            info = get_for_loop_info(
                node
            )

            findings.append({
                "type": "loop",
                "loop": get_text(node),
                "variable": info[
                    "variable"
                ],
                "variable_changes": True,
                "infinite_loop_risk": False,
                "location": node_location(
                    node
                ),
                "risk": (
                    "Possible excessive "
                    "iteration"
                )
            })

        # ====================================================
        # ARRAY ACCESS
        # ====================================================

        if node.type == "subscript_expression":

            expression = get_text(
                node
            )

            identifiers = []

            def find_identifiers(child):

                if child.type == "identifier":

                    identifiers.append(
                        get_text(child)
                    )

                for subchild in child.children:

                    find_identifiers(
                        subchild
                    )

            find_identifiers(
                node
            )

            array_name = None
            index_variable = None
            index_position = None

            if len(identifiers) >= 1:

                array_name = identifiers[0]

            if len(identifiers) >= 2:

                possible_index = identifiers[1]

                if (
                    possible_index
                    in input_variables
                ):

                    index_variable = (
                        possible_index
                    )

                    index_position = (
                        input_variables.index(
                            possible_index
                        ) + 1
                    )

            array_info = arrays.get(
                array_name
            )

            # ------------------------------------------------
            # EXACT SOURCE LOCATION
            # ------------------------------------------------

            location = node_location(
                node
            )

            if array_info:

                findings.append({
                    "type": "array_access",
                    "expression": expression,
                    "array": array_name,
                    "index_variable": index_variable,
                    "index_position": index_position,
                    "array_size": array_info[
                        "size"
                    ],
                    "size_variable": array_info[
                        "size_variable"
                    ],
                    "size_position": (
                        input_variables.index(
                            array_info[
                                "size_variable"
                            ]
                        ) + 1
                        if (
                            array_info[
                                "size_variable"
                            ]
                            in input_variables
                        )
                        else None
                    ),
                    "min_index": array_info[
                        "min_index"
                    ],
                    "max_index": array_info[
                        "max_index"
                    ],
                    "location": location,
                    "risk": (
                        "Possible out-of-bounds "
                        "access"
                    )
                })

            else:

                findings.append({
                    "type": "array_access",
                    "expression": expression,
                    "array": array_name,
                    "index_variable": index_variable,
                    "index_position": index_position,
                    "array_size": None,
                    "size_variable": None,
                    "size_position": None,
                    "min_index": None,
                    "max_index": None,
                    "location": location,
                    "risk": (
                        "Possible out-of-bounds "
                        "access"
                    )
                })

        for child in node.children:

            analyze_operations(
                child
            )

    # ========================================================
    # RUN
    # ========================================================

    collect_input_variables(
        root
    )

    input_variables = list(
        dict.fromkeys(
            input_variables
        )
    )

    collect_variable_types(
        root
    )

    collect_arrays(
        root
    )

    analyze_operations(
        root
    )

    analyze_arithmetic(
        root
    )

    analyze_complexity(
        root
    )

    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    unique_findings = []
    seen = set()

    for finding in findings:

        key = str(
            sorted(
                finding.items()
            )
        )

        if key not in seen:

            seen.add(
                key
            )

            unique_findings.append(
                finding
            )

    findings = unique_findings

    # ========================================================
    # RESULT
    # ========================================================

    return {
        "inputs": input_variables,
        "arrays": arrays,
        "variable_types": variable_types,
        "findings": findings
    }


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    code = """
    #include <iostream>
    using namespace std;

    int main() {

        int n;

        cin >> n;

        int arr[5] = {0, 1, 2, 3, 4};

        cout << arr[n];

        return 0;
    }
    """

    result = analyze_code(
        code
    )

    print(
        "================================"
    )

    print(
        "CODE ANALYSIS"
    )

    print(
        "================================"
    )

    print(
        "Inputs:"
    )

    for i, variable in enumerate(
        result["inputs"],
        start=1
    ):

        print(
            f"Position {i} -> {variable}"
        )

    print()

    print(
        "Variable types:"
    )

    for name, variable_type in (
        result["variable_types"].items()
    ):

        print(
            f"{name}: {variable_type}"
        )

    print()

    print(
        "Arrays:"
    )

    if result["arrays"]:

        for name, info in (
            result["arrays"].items()
        ):

            print(
                f"{name}: "
                f"size={info['size']}, "
                f"valid indexes="
                f"{info['min_index']}-"
                f"{info['max_index']}"
            )

    else:

        print(
            "No arrays detected."
        )

    print()

    print(
        "Findings:"
    )

    for finding in result[
        "findings"
    ]:

        print(
            finding
        )

        print(
            "--------------------------------"
        )