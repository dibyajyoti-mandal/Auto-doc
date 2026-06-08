import yaml
from pathlib import Path


class MappingRegistry:
    """
    Registry that maps upstream repository source file paths to target
    documentation page paths in the website repository.
    """

    def __init__(self, mappings: dict):
        self.mappings = mappings

    @classmethod
    def load(cls, path: str) -> "MappingRegistry":
        resolved = Path(path).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Mappings file not found: {resolved}")

        with open(resolved) as f:
            data = yaml.safe_load(f)

        if not data or "mappings" not in data:
            raise ValueError(f"Invalid mappings file: missing top-level 'mappings' key in {resolved}")

        return cls(data["mappings"])

    def resolve(self, repo: str, source_path: str) -> dict | None:
        """
        Resolve a source file path from an upstream repo to its target
        documentation page configuration.
        """
        repo_mappings = self.mappings.get(repo)
        if not repo_mappings:
            return None

        for prefix, config in repo_mappings.items():
            if source_path.startswith(prefix):
                return config

        return None 

    def list_repos(self) -> list[str]:
        return list(self.mappings.keys())
