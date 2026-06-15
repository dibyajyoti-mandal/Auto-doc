import pytest
import yaml
from pathlib import Path
from unittest.mock import mock_open, patch

from utils.register import MappingRegistry



SAMPLE_YAML = """
mappings:
  dibyajyoti-mandal/krknctl:
    cmd/:
      target: content/en/docs/reference/cli.md
      change_type: cli_flag
    pkg/scenario/:
      target: content/en/docs/scenarios/_index.md
      change_type: new_scenario
"""

SAMPLE_DATA = yaml.safe_load(SAMPLE_YAML)


@pytest.fixture
def registry():
    return MappingRegistry(SAMPLE_DATA["mappings"])


# MappingRegistry.load

class TestMappingRegistryLoad:
    def test_load_valid_file(self, tmp_path):
        mapping_file = tmp_path / "mappings.yaml"
        mapping_file.write_text(SAMPLE_YAML)
        reg = MappingRegistry.load(str(mapping_file))
        assert isinstance(reg, MappingRegistry)

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            MappingRegistry.load(str(tmp_path / "nonexistent.yaml"))

    def test_load_missing_mappings_key_raises(self, tmp_path):
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("something: else\n")
        with pytest.raises(ValueError, match="missing top-level 'mappings' key"):
            MappingRegistry.load(str(bad_file))

    def test_load_empty_file_raises(self, tmp_path):
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")
        with pytest.raises(ValueError):
            MappingRegistry.load(str(empty_file))


# MappingRegistry.resolve

class TestMappingRegistryResolve:
    def test_resolves_known_prefix(self, registry):
        result = registry.resolve("dibyajyoti-mandal/krknctl", "cmd/run.go")
        assert result is not None
        assert result["target"] == "content/en/docs/reference/cli.md"
        assert result["change_type"] == "cli_flag"

    def test_resolves_nested_path(self, registry):
        result = registry.resolve("dibyajyoti-mandal/krknctl", "pkg/scenario/pod_disruption.go")
        assert result is not None
        assert result["target"] == "content/en/docs/scenarios/_index.md"

    def test_returns_none_for_unknown_path(self, registry):
        result = registry.resolve("dibyajyoti-mandal/krknctl", "internal/utils/helper.go")
        assert result is None

    def test_returns_none_for_unknown_repo(self, registry):
        result = registry.resolve("some/other-repo", "cmd/run.go")
        assert result is None

    def test_list_repos(self, registry):
        repos = registry.list_repos()
        assert "dibyajyoti-mandal/krknctl" in repos
