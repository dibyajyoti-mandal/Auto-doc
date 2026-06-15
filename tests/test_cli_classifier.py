import pytest
from analyzer.classifiers.cli import (
    _extract_file_content_from_diff,
    _reconstruct_old_version,
    _parse_flags_from_ast,
    _diff_flags,
    _build_parser,
    classify,
)


# Shared diff fixtures

DIFF_ADD_FLAG = """\
diff --git a/cmd/run.go b/cmd/run.go
index abc..def 100644
--- a/cmd/run.go
+++ b/cmd/run.go
@@ -1,5 +1,6 @@
 package cmd
 func init() {
-    cmd.Flags().String("output", "json", "output format")
+    cmd.Flags().String("output", "json", "output format")
+    cmd.Flags().String("timeout", "30s", "request timeout")
 }
"""

DIFF_REMOVE_FLAG = """\
diff --git a/cmd/run.go b/cmd/run.go
index abc..def 100644
--- a/cmd/run.go
+++ b/cmd/run.go
@@ -1,5 +1,4 @@
 package cmd
 func init() {
-    cmd.Flags().String("timeout", "30s", "request timeout")
     cmd.Flags().String("output", "json", "output format")
 }
"""

DIFF_NEW_COMMAND = """\
diff --git a/cmd/list.go b/cmd/list.go
index abc..def 100644
--- a/cmd/list.go
+++ b/cmd/list.go
@@ -1,3 +1,6 @@
 package cmd
+var listCmd = &cobra.Command{
+    Use: "list",
+}
"""

DIFF_TEST_ONLY = """\
diff --git a/cmd/run_test.go b/cmd/run_test.go
index abc..def 100644
--- a/cmd/run_test.go
+++ b/cmd/run_test.go
@@ -1,1 +1,2 @@
 package cmd
+// test only
"""

GO_SOURCE_WITH_FLAGS = """\
package cmd

import "github.com/spf13/cobra"

func init() {
    cmd.Flags().String("output", "json", "output format")
    cmd.PersistentFlags().Bool("verbose", false, "enable verbose logging")
    cmd.Flags().StringP("namespace", "n", "default", "target namespace")
}
"""

GO_SOURCE_EMPTY = "package cmd\n"


# _extract_file_content_from_diff / _reconstruct_old_version

class TestDiffReconstruction:
    def test_extract_new_version_includes_added_lines(self):
        content = _extract_file_content_from_diff(DIFF_ADD_FLAG, "cmd/run.go")
        assert "timeout" in content
        assert "output" in content

    def test_extract_new_version_excludes_removed_lines(self):
        content = _extract_file_content_from_diff(DIFF_REMOVE_FLAG, "cmd/run.go")
        assert "timeout" not in content

    def test_reconstruct_old_version_includes_removed_lines(self):
        content = _reconstruct_old_version(DIFF_REMOVE_FLAG, "cmd/run.go")
        assert "timeout" in content

    def test_reconstruct_old_version_excludes_added_lines(self):
        content = _reconstruct_old_version(DIFF_ADD_FLAG, "cmd/run.go")
        assert "timeout" not in content

    def test_wrong_filepath_returns_empty(self):
        content = _extract_file_content_from_diff(DIFF_ADD_FLAG, "cmd/other.go")
        assert content.strip() == ""


# _parse_flags_from_ast

class TestParseFlagsFromAst:
    def setup_method(self):
        self.parser = _build_parser()

    def test_detects_string_flag(self):
        flags = _parse_flags_from_ast(GO_SOURCE_WITH_FLAGS, self.parser)
        names = [f["name"] for f in flags]
        assert "output" in names

    def test_detects_bool_flag(self):
        flags = _parse_flags_from_ast(GO_SOURCE_WITH_FLAGS, self.parser)
        names = [f["name"] for f in flags]
        assert "verbose" in names

    def test_detects_shorthand_flag(self):
        flags = _parse_flags_from_ast(GO_SOURCE_WITH_FLAGS, self.parser)
        ns_flag = next((f for f in flags if f["name"] == "namespace"), None)
        assert ns_flag is not None
        assert ns_flag["shorthand"] is True

    def test_flag_has_expected_fields(self):
        flags = _parse_flags_from_ast(GO_SOURCE_WITH_FLAGS, self.parser)
        output_flag = next(f for f in flags if f["name"] == "output")
        assert output_flag["type"] == "string"
        assert output_flag["default"] == "json"
        assert "output format" in output_flag["usage"]

    def test_empty_source_returns_no_flags(self):
        flags = _parse_flags_from_ast(GO_SOURCE_EMPTY, self.parser)
        assert flags == []


# _diff_flags

class TestDiffFlags:
    def test_added_flag_detected(self):
        old = [{"name": "output", "type": "string"}]
        new = [{"name": "output", "type": "string"}, {"name": "timeout", "type": "string"}]
        added, removed = _diff_flags(old, new)
        assert len(added) == 1
        assert added[0]["name"] == "timeout"
        assert removed == []

    def test_removed_flag_detected(self):
        old = [{"name": "output", "type": "string"}, {"name": "timeout", "type": "string"}]
        new = [{"name": "output", "type": "string"}]
        added, removed = _diff_flags(old, new)
        assert added == []
        assert len(removed) == 1
        assert removed[0]["name"] == "timeout"

    def test_no_change_returns_empty(self):
        flags = [{"name": "output", "type": "string"}]
        added, removed = _diff_flags(flags, flags)
        assert added == []
        assert removed == []

    def test_renamed_flag_appears_as_add_and_remove(self):
        old = [{"name": "out", "type": "string"}]
        new = [{"name": "output", "type": "string"}]
        added, removed = _diff_flags(old, new)
        assert len(added) == 1
        assert len(removed) == 1


# classify (integration of the full classifier)

class TestClassify:
    def test_returns_none_for_test_only_diff(self):
        assert classify(DIFF_TEST_ONLY) is None

    def test_detects_new_command(self):
        result = classify(DIFF_NEW_COMMAND)
        assert result is not None
        assert result["type"] == "cli_flag"
        assert "list" in result["commands_added"]

    def test_result_has_source_paths(self):
        result = classify(DIFF_NEW_COMMAND)
        assert "source_paths" in result
        assert isinstance(result["source_paths"], list)

    def test_returns_none_for_empty_diff(self):
        assert classify("") is None
