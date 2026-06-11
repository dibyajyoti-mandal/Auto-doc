import json
import sys
from pathlib import Path

from analyzer.noise_filter import is_noise
from analyzer.classifiers import cli_classifier, readme_classifier
from utils.register import MappingRegistry


MAPPINGS_PATH = "mappings/mappings.yaml"
METADATA_PATH = "metadata.json"
OUTPUT_PATH = "change_payload.json"


def main():
    # 1. Load metadata
    metadata_path = Path(METADATA_PATH)
    if not metadata_path.exists():
        print("ERROR: metadata.json not found.")
        sys.exit(1)

    with open(metadata_path) as f:
        metadata = json.load(f)

    repo = metadata["repo"]
    pr_number = metadata["pr_number"]
    pr_title  = metadata["pr_title"]
    diff = metadata["diff"]

    # 2. Noise filter
    if is_noise(diff):
        print("No documentation-relevant changes detected. Skipping.")
        sys.exit(0)

    # 3. Load mapping registry
    registry = MappingRegistry.load(MAPPINGS_PATH)

    # 4. Run classifiers
    classifiers = [cli_classifier, readme_classifier]
    changes = []

    for clf in classifiers:
        result = clf.classify(diff)
        if result is None:
            continue

        # Resolve target page from registry using the first matched source path
        source_paths = result.get("source_paths", [])
        resolved = None
        for sp in source_paths:
            resolved = registry.resolve(repo, sp)
            if resolved:
                break

        if resolved:
            result["target_page"] = resolved["target"]
        else:
            print(f"WARNING: No mapping found for {source_paths} in {repo}. Skipping.")
            continue

        changes.append(result)

    # 5. Nothing relevant after classification
    if not changes:
        print("No documentation-relevant changes detected after classification. Skipping.")
        sys.exit(0)

    # 6. Write change_payload.json
    payload = {
        "repo": repo,
        "pr_number": pr_number,
        "pr_title": pr_title,
        "changes": changes,
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"change_payload.json written with {len(changes)} change(s).")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
