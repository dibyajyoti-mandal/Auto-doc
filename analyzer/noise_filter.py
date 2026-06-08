import re

NOISE_PATTERNS  = {
    r".*_test\.go$",
    r"^\.github/",
    r"^vendor/",
    r".*\.sum$",
    r"^Makefile$",
    r".*\.mod$",
}

def extract_changed_files(diff: str) -> list[str]:
    """
    Extract changed file paths from a unified diff by reading
    'diff --git a/path b/path' header lines.
    """
    files = []
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            match = re.match(r"diff --git a/(.+) b/(.+)", line)
            if match:
                files.append(match.group(2))
    return files

def is_noise(diff: str) -> bool:
    """
    Returns True if ALL changed files match noise patterns,
    meaning no documentation-relevant changes exist.
    """
    files = extract_changed_files(diff)

    if not files:
        return True

    for filepath in files:
        if not any(re.match(pattern, filepath) for pattern in NOISE_PATTERNS):
            return False

    return True 