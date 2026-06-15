"""
tests/test_noise_filter.py

Unit tests for analyzer.noise_filter
"""
import pytest
from analyzer.noise_filter import extract_changed_files, is_noise


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DIFF_GO_ONLY = """\
diff --git a/cmd/run.go b/cmd/run.go
index abc..def 100644
--- a/cmd/run.go
+++ b/cmd/run.go
@@ -1,3 +1,4 @@
 package cmd
+// new comment
"""

DIFF_TEST_ONLY = """\
diff --git a/cmd/run_test.go b/cmd/run_test.go
index abc..def 100644
--- a/cmd/run_test.go
+++ b/cmd/run_test.go
@@ -1,1 +1,2 @@
 package cmd
+// test change
"""

DIFF_MIXED = """\
diff --git a/cmd/run.go b/cmd/run.go
index abc..def 100644
--- a/cmd/run.go
+++ b/cmd/run.go
@@ -1,1 +1,2 @@
 package cmd
+// real change
diff --git a/cmd/run_test.go b/cmd/run_test.go
index abc..def 100644
--- a/cmd/run_test.go
+++ b/cmd/run_test.go
@@ -1,1 +1,2 @@
 package cmd
+// test change
"""

DIFF_VENDOR = """\
diff --git a/vendor/some/pkg/file.go b/vendor/some/pkg/file.go
index abc..def 100644
--- a/vendor/some/pkg/file.go
+++ b/vendor/some/pkg/file.go
@@ -1,1 +1,1 @@
-old
+new
"""

DIFF_GITHUB_CI = """\
diff --git a/.github/workflows/ci.yaml b/.github/workflows/ci.yaml
index abc..def 100644
--- a/.github/workflows/ci.yaml
+++ b/.github/workflows/ci.yaml
@@ -1,1 +1,2 @@
 name: CI
+  new-step: true
"""

DIFF_EMPTY = ""


# extract_changed_files

class TestExtractChangedFiles:
    def test_extracts_single_file(self):
        files = extract_changed_files(DIFF_GO_ONLY)
        assert files == ["cmd/run.go"]

    def test_extracts_multiple_files(self):
        files = extract_changed_files(DIFF_MIXED)
        assert "cmd/run.go" in files
        assert "cmd/run_test.go" in files
        assert len(files) == 2

    def test_empty_diff_returns_empty_list(self):
        assert extract_changed_files(DIFF_EMPTY) == []

    def test_extracts_vendor_file(self):
        files = extract_changed_files(DIFF_VENDOR)
        assert files == ["vendor/some/pkg/file.go"]


# is_noise

class TestIsNoise:
    def test_test_file_only_is_noise(self):
        assert is_noise(DIFF_TEST_ONLY) is True

    def test_vendor_file_only_is_noise(self):
        assert is_noise(DIFF_VENDOR) is True

    def test_ci_yaml_is_noise(self):
        assert is_noise(DIFF_GITHUB_CI) is True

    def test_real_go_file_is_not_noise(self):
        assert is_noise(DIFF_GO_ONLY) is False

    def test_mixed_diff_is_not_noise(self):
        # One real file present → not noise
        assert is_noise(DIFF_MIXED) is False

    def test_empty_diff_is_noise(self):
        assert is_noise(DIFF_EMPTY) is True
