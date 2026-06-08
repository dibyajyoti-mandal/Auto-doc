import re
from analyzer.noise_filter import extract_changed_files


# Matches lines like:
# .Flags().String("flag-name", "default", "usage string")
# .PersistentFlags().BoolP("flag-name", "f", false, "usage string")
FLAG_PATTERN = re.compile(
    r'\.(?:Persistent)?Flags\(\)\.(String|Bool|Int|Int64|Float64|StringSlice|StringArray)(P?)\('
    r'"([^"]+)",\s*'        # flag name
    r'(?:"[^"]*",\s*)?'    # optional shorthand (only in P-variants)
    r'([^,]+),\s*'          # default value
    r'"([^"]*)"'            # usage string
    r'\)'
)

# Matches Use: "subcommand" inside a Command{} struct
COMMAND_USE_PATTERN = re.compile(r'Use:\s*"([^"]+)"')


def _parse_flags_from_diff(diff: str) -> tuple[list[dict], list[dict]]:
    """
    Walk the diff line by line. Lines starting with '+' are additions,
    lines starting with '-' are removals. Skip diff header lines ('+++ / ---').
    """
    added = []
    removed = []

    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue

        if line.startswith("+") or line.startswith("-"):
            match = FLAG_PATTERN.search(line)
            if match:
                flag = {
                    "type": match.group(1).lower(),   # string / bool / int etc.
                    "shorthand": match.group(2) == "P",  # True if P-variant
                    "name": match.group(3),
                    "default": match.group(4).strip(),
                    "usage": match.group(5),
                }
                if line.startswith("+"):
                    added.append(flag)
                else:
                    removed.append(flag)

    return added, removed


def _parse_commands_from_diff(diff: str) -> tuple[list[str], list[str]]:
    """
    Detect added/removed cobra Command Use: fields in the diff.
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


def classify(diff: str) -> dict | None:
    """
    Returns a classification payload if any cobra CLI changes are detected,
    otherwise returns None.
    """
    # only look at .go files that are not test files
    changed_files = [
        f for f in extract_changed_files(diff)
        if f.endswith(".go") and not f.endswith("_test.go")
    ]

    if not changed_files:
        return None

    flags_added, flags_removed = _parse_flags_from_diff(diff)
    commands_added, commands_removed = _parse_commands_from_diff(diff)

    # nothing cobra-related found
    if not any([flags_added, flags_removed, commands_added, commands_removed]):
        return None

    return {
        "type": "cli_flag",
        "source_paths": changed_files,  # all changed .go files in this PR
        "flags_added": flags_added,
        "flags_removed": flags_removed,
        "commands_added": commands_added,
        "commands_removed": commands_removed,
    }