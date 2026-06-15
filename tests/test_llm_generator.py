import json
import pytest
from unittest.mock import MagicMock, patch, call

from llm.llm_generator import build_user_prompt, call_llm_with_retry



def _make_groq_response(content: str):
    """Build a mock Groq chat completion response."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


VALID_LLM_JSON = json.dumps({
    "updated_markdown": "# Docs\n\nUpdated content.",
    "pr_summary": "Added timeout flag.",
    "modified_sections": ["CLI Flags"],
})

FENCED_LLM_JSON = f"```json\n{VALID_LLM_JSON}\n```"
BARE_FENCED_LLM_JSON = f"```\n{VALID_LLM_JSON}\n```"

# Literal newline in JSON string (strict=False needed)
LITERAL_NEWLINE_JSON = '{"updated_markdown": "line1\nline2", "pr_summary": "x", "modified_sections": []}'


# build_user_prompt

class TestBuildUserPrompt:
    def test_includes_existing_content(self):
        payload = {"repo": "org/repo", "pr_number": "1", "pr_title": "Add flag", "changes": []}
        prompt = build_user_prompt("## Existing docs", payload)
        assert "## Existing docs" in prompt

    def test_new_page_message_when_content_empty(self):
        payload = {"repo": "org/repo", "pr_number": "1", "pr_title": "Add flag", "changes": []}
        prompt = build_user_prompt("", payload)
        assert "new page" in prompt.lower() or "scratch" in prompt.lower()

    def test_includes_repo_and_pr_info(self):
        payload = {"repo": "org/repo", "pr_number": "42", "pr_title": "My PR", "changes": []}
        prompt = build_user_prompt("content", payload)
        assert "org/repo" in prompt
        assert "42" in prompt
        assert "My PR" in prompt

    def test_changes_serialised_as_json(self):
        changes = [{"type": "cli_flag", "flags_added": [{"name": "timeout"}]}]
        payload = {"repo": "org/repo", "pr_number": "1", "pr_title": "T", "changes": changes}
        prompt = build_user_prompt("content", payload)
        assert "timeout" in prompt


# call_llm_with_retry

class TestCallLlmWithRetry:
    def _make_client(self, content: str):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_groq_response(content)
        return client

    def test_returns_parsed_json_on_success(self):
        client = self._make_client(VALID_LLM_JSON)
        result = call_llm_with_retry(client, "prompt")
        assert result["pr_summary"] == "Added timeout flag."

    def test_strips_json_fence(self):
        client = self._make_client(FENCED_LLM_JSON)
        result = call_llm_with_retry(client, "prompt")
        assert "updated_markdown" in result

    def test_strips_bare_fence(self):
        client = self._make_client(BARE_FENCED_LLM_JSON)
        result = call_llm_with_retry(client, "prompt")
        assert "updated_markdown" in result

    def test_handles_literal_newlines_in_json(self):
        client = self._make_client(LITERAL_NEWLINE_JSON)
        result = call_llm_with_retry(client, "prompt")
        assert "line1" in result["updated_markdown"]

    @patch("llm.llm_generator.time.sleep")
    def test_retries_on_transient_error(self, mock_sleep):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            Exception("rate limit"),
            Exception("rate limit"),
            _make_groq_response(VALID_LLM_JSON),
        ]
        result = call_llm_with_retry(client, "prompt", retries=3)
        assert result["pr_summary"] == "Added timeout flag."
        assert client.chat.completions.create.call_count == 3

    @patch("llm.llm_generator.time.sleep")
    def test_raises_after_all_retries_exhausted(self, mock_sleep):
        client = MagicMock()
        client.chat.completions.create.side_effect = Exception("persistent error")
        with pytest.raises(Exception, match="persistent error"):
            call_llm_with_retry(client, "prompt", retries=3)
        assert client.chat.completions.create.call_count == 3

    @patch("llm.llm_generator.time.sleep")
    def test_exponential_backoff_sleep_values(self, mock_sleep):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            Exception("err"),
            Exception("err"),
            _make_groq_response(VALID_LLM_JSON),
        ]
        call_llm_with_retry(client, "prompt", retries=3)
        sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert sleep_calls == [1, 2]  # 2^0, 2^1
