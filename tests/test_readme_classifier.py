import pytest
from analyzer.classifiers.readme import classify, _extract_modified_paragraphs



# Fixtures

DIFF_MD_CHANGE = """\
diff --git a/README.md b/README.md
index abc..def 100644
--- a/README.md
+++ b/README.md
@@ -1,3 +1,4 @@
 # krkn
-Old description line.
+New description line.
+Added a new paragraph here.
"""

DIFF_GO_ONLY = """\
diff --git a/cmd/run.go b/cmd/run.go
index abc..def 100644
--- a/cmd/run.go
+++ b/cmd/run.go
@@ -1,1 +1,2 @@
 package cmd
+// a comment
"""

DIFF_MD_AND_GO = """\
diff --git a/README.md b/README.md
index abc..def 100644
--- a/README.md
+++ b/README.md
@@ -1,1 +1,2 @@
 # krkn
+new line
diff --git a/cmd/run.go b/cmd/run.go
index abc..def 100644
--- a/cmd/run.go
+++ b/cmd/run.go
@@ -1,1 +1,2 @@
 package cmd
+// comment
"""


# _extract_modified_paragraphs

class TestExtractModifiedParagraphs:
    def test_captures_added_lines(self):
        result = _extract_modified_paragraphs(DIFF_MD_CHANGE)
        assert "+New description line." in result
        assert "+Added a new paragraph here." in result

    def test_captures_removed_lines(self):
        result = _extract_modified_paragraphs(DIFF_MD_CHANGE)
        assert "-Old description line." in result

    def test_skips_diff_headers(self):
        result = _extract_modified_paragraphs(DIFF_MD_CHANGE)
        assert "+++" not in result
        assert "---" not in result

    def test_empty_diff_returns_empty_string(self):
        assert _extract_modified_paragraphs("") == ""


# classify

class TestReadmeClassify:
    def test_detects_md_file_change(self):
        result = classify(DIFF_MD_CHANGE)
        assert result is not None
        assert result["type"] == "readme"

    def test_source_paths_contains_md_file(self):
        result = classify(DIFF_MD_CHANGE)
        assert "README.md" in result["source_paths"]

    def test_diff_excerpt_is_populated(self):
        result = classify(DIFF_MD_CHANGE)
        assert result["diff_excerpt"] != ""

    def test_returns_none_for_go_only_diff(self):
        assert classify(DIFF_GO_ONLY) is None

    def test_detects_md_in_mixed_diff(self):
        result = classify(DIFF_MD_AND_GO)
        assert result is not None
        assert any(p.endswith(".md") for p in result["source_paths"])

    def test_returns_none_for_empty_diff(self):
        assert classify("") is None
