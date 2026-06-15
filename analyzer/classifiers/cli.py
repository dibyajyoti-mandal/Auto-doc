import re
from analyzer.noise_filter import extract_changed_files
import tree_sitter_go as tsg
from tree_sitter import Language, Parser

GO_LANGUAGE = Language(tsg.language(), "go")

COMMAND_USE_PATTERN = re.compile(r'Use:\s*"([^"]+)"')


def _build_parser() -> Parser:
    parser = Parser()
    parser.set_language(GO_LANGUAGE)
    return parser


def _extract_file_content_from_diff(diff: str, filepath: str) -> str:
    """
    Reconstruct the post-change version of a file from the diff.
    Takes all non-removed lines from the relevant file section.
    """
    lines = []
    in_file = False

    for line in diff.splitlines():
        if line.startswith("diff --git"):
            in_file = f"b/{filepath}" in line
            continue
        if not in_file:
            continue
        # skip diff headers
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        # skip removed lines
        if line.startswith("-"):
            continue
        # keep context lines and added lines (strip the leading +)
        if line.startswith("+"):
            lines.append(line[1:])
        else:
            lines.append(line)

    return "\n".join(lines)


def _parse_flags_from_ast(source: str, parser: Parser) -> list[dict]:
    """
    Walk the AST to find all cobra flag definitions.
    Handles both single-line and multiline definitions.
    """
    tree = parser.parse(bytes(source, "utf8"))
    flags = []

    def walk(node):
        # Looking for call_expression nodes
        if node.type == "call_expression":
            text = source[node.start_byte:node.end_byte]

            # Match .Flags().XxxP?( patterns
            method_match = re.search(
                r'\.(?:Persistent)?Flags\(\)\.'
                r'(String|Bool|Int|Int64|Float64|StringSlice|StringArray)(P?)\(',
                text
            )
            if method_match:
                flag_type = method_match.group(1).lower()
                is_shorthand = method_match.group(2) == "P"

                # Extract string arguments from the argument list
                args = _extract_string_args(node, source)

                if is_shorthand and len(args) >= 4:
                    # StringP("name", "shorthand", "default", "usage")
                    flags.append({
                        "type": flag_type,
                        "shorthand": True,
                        "name": args[0],
                        "default": args[2],
                        "usage": args[3],
                    })
                elif not is_shorthand and len(args) >= 3:
                    # String("name", "default", "usage")
                    flags.append({
                        "type": flag_type,
                        "shorthand": False,
                        "name": args[0],
                        "default": args[1],
                        "usage": args[2],
                    })

        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return flags


def _extract_string_args(call_node, source: str) -> list[str]:
    """
    Extract string literal and identifier arguments from a call expression node.
    Returns raw values (without quotes for strings).
    """
    args = []
    for child in call_node.children:
        if child.type == "argument_list":
            for arg in child.children:
                if arg.type == "interpreted_string_literal":
                    # strip surrounding double-quotes
                    args.append(source[arg.start_byte:arg.end_byte].strip('"'))
                elif arg.type == "raw_string_literal":
                    # strip surrounding backticks
                    args.append(source[arg.start_byte:arg.end_byte].strip('`'))
                elif arg.type in ("identifier", "false", "true", "int_literal", "float_literal"):
                    args.append(source[arg.start_byte:arg.end_byte])
    return args


def _diff_flags(
    old_flags: list[dict],
    new_flags: list[dict]
) -> tuple[list[dict], list[dict]]:
    """
    Compare old and new flag lists by name to produce added/removed sets.
    """
    old_by_name = {f["name"]: f for f in old_flags}
    new_by_name = {f["name"]: f for f in new_flags}

    added = [f for name, f in new_by_name.items() if name not in old_by_name]
    removed = [f for name, f in old_by_name.items() if name not in new_by_name]

    return added, removed


def _parse_commands_from_diff(diff: str) -> tuple[list[str], list[str]]:
    """
    Detect added/removed cobra Command Use: fields from diff lines.
    AST-level command detection is not needed here since Use: is always single-line.
    """
    added = []
    removed = []

    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+") or line.startswith("-"):
            match = COMMAND_USE_PATTERN.search(line)
            if match:
                cmd_name = match.group(1)
                if line.startswith("+"):
                    added.append(cmd_name)
                else:
                    removed.append(cmd_name)

    return added, removed


def _reconstruct_old_version(diff: str, filepath: str) -> str:
    """
    Reconstruct the pre-change version of a file from the diff.
    Takes all non-added lines from the relevant file section.
    """
    lines = []
    in_file = False

    for line in diff.splitlines():
        if line.startswith("diff --git"):
            in_file = f"b/{filepath}" in line
            continue
        if not in_file:
            continue
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            continue  # skip added lines
        if line.startswith("-"):
            lines.append(line[1:])  # restore removed lines
        else:
            lines.append(line)

    return "\n".join(lines)


def classify(diff: str) -> dict | None:
    """
    Returns a classification payload if any cobra CLI changes are detected,
    otherwise returns None.
    """
    changed_files = [
        f for f in extract_changed_files(diff)
        if f.endswith(".go") and not f.endswith("_test.go")
    ]

    if not changed_files:
        return None

    parser = _build_parser()
    all_flags_added = []
    all_flags_removed = []

    for filepath in changed_files:
        old_source = _reconstruct_old_version(diff, filepath)
        new_source = _extract_file_content_from_diff(diff, filepath)

        old_flags = _parse_flags_from_ast(old_source, parser) if old_source.strip() else []
        new_flags = _parse_flags_from_ast(new_source, parser) if new_source.strip() else []

        added, removed = _diff_flags(old_flags, new_flags)
        all_flags_added.extend(added)
        all_flags_removed.extend(removed)

    commands_added, commands_removed = _parse_commands_from_diff(diff)

    if not any([all_flags_added, all_flags_removed, commands_added, commands_removed]):
        return None

    return {
        "type": "cli_flag",
        "source_paths": changed_files,
        "flags_added": all_flags_added,
        "flags_removed": all_flags_removed,
        "commands_added": commands_added,
        "commands_removed": commands_removed,
    }