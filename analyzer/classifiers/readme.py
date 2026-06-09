import re
from analyzer.noise_filter import extract_changed_files


def _extract_modified_paragraphs(diff: str) -> str:
    """
    Pull out added/removed lines from .md files in the diff.
    Skips diff header lines.
    """
    excerpts = []

    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+") or line.startswith("-"):
            excerpts.append(line)

    return "\n".join(excerpts)


def classify(diff: str) -> dict | None:
    """
    Returns a classification payload if any .md files were changed,
    otherwise returns None.
    """
    changed_files = [
        f for f in extract_changed_files(diff)
        if f.endswith(".md")
    ]

    if not changed_files:
        return None

    excerpt = _extract_modified_paragraphs(diff)

    return {
        "type": "readme",
        "source_paths": changed_files,
        "diff_excerpt": excerpt,
    }