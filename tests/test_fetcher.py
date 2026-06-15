import base64
import pytest
from unittest.mock import MagicMock, patch

from llm.fetcher import fetch_target_page


SAMPLE_CONTENT = "# CLI Reference\n\nSome docs here.\n"
SAMPLE_CONTENT_B64 = base64.b64encode(SAMPLE_CONTENT.encode()).decode()


class TestFetchTargetPage:
    @patch("llm.fetcher.requests.get")
    def test_returns_decoded_content_on_200(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"content": SAMPLE_CONTENT_B64}
        mock_get.return_value = mock_resp

        result = fetch_target_page("content/cli.md", "tok", "org/repo")

        assert result == SAMPLE_CONTENT

    @patch("llm.fetcher.requests.get")
    def test_returns_empty_string_on_404(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        result = fetch_target_page("content/missing.md", "tok", "org/repo")

        assert result == ""

    @patch("llm.fetcher.requests.get")
    def test_raises_on_non_404_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = Exception("Server Error")
        mock_get.return_value = mock_resp

        with pytest.raises(Exception, match="Server Error"):
            fetch_target_page("content/cli.md", "tok", "org/repo")

    @patch("llm.fetcher.requests.get")
    def test_sends_correct_auth_header(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"content": SAMPLE_CONTENT_B64}
        mock_get.return_value = mock_resp

        fetch_target_page("content/cli.md", "mytoken", "org/repo")

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer mytoken"

    @patch("llm.fetcher.requests.get")
    def test_constructs_correct_url(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"content": SAMPLE_CONTENT_B64}
        mock_get.return_value = mock_resp

        fetch_target_page("content/cli.md", "tok", "org/myrepo")

        url = mock_get.call_args[0][0]
        assert "org/myrepo" in url
        assert "content/cli.md" in url
