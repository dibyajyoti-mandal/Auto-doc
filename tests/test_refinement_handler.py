import json
import pytest
from unittest.mock import MagicMock, patch

from refinement.handler import parse_command, build_refinement_prompt, call_llm


def _make_groq_response(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


VALID_RESPONSE = json.dumps({
    "updated_markdown": "# Updated\nContent here.",
    "reply": "Expanded the CLI Flags section.",
})

FENCED_RESPONSE = f"```json\n{VALID_RESPONSE}\n```"
LITERAL_NEWLINE_RESPONSE = '{"updated_markdown": "line1\nline2", "reply": "done"}'


# parse_command

class TestParseCommand:
    @pytest.mark.parametrize("comment,expected_cmd,has_arg", [
        ("@krkn-docs-bot expand CLI Flags", "expand", True),
        ("@krkn-docs-bot fix Remove the duplicate line", "fix", True),
        ("@krkn-docs-bot regenerate", "regenerate", False),
        ("@krkn-docs-bot add example", "add example", False),
    ])
    def test_recognises_all_commands(self, comment, expected_cmd, has_arg):
        cmd, arg = parse_command(comment)
        assert cmd == expected_cmd
        if has_arg:
            assert arg != ""
        else:
            assert arg == ""

    def test_case_insensitive(self):
        cmd, arg = parse_command("@KRKN-DOCS-BOT EXPAND intro")
        assert cmd == "expand"

    def test_returns_none_for_unrecognised_comment(self):
        cmd, arg = parse_command("just a normal comment")
        assert cmd is None
        assert arg is None

    def test_returns_none_for_empty_string(self):
        cmd, arg = parse_command("")
        assert cmd is None

    def test_expand_captures_section_name(self):
        _, arg = parse_command("@krkn-docs-bot expand CLI Flags section")
        assert "CLI Flags" in arg


# build_refinement_prompt

class TestBuildRefinementPrompt:
    def test_expand_instruction_contains_argument(self):
        prompt = build_refinement_prompt("existing docs", "expand", "CLI Flags")
        assert "CLI Flags" in prompt
        assert "more detail" in prompt.lower()

    def test_fix_instruction_contains_argument(self):
        prompt = build_refinement_prompt("existing docs", "fix", "remove duplicate line")
        assert "remove duplicate line" in prompt

    def test_regenerate_instruction_mentions_front_matter(self):
        prompt = build_refinement_prompt("existing docs", "regenerate", "")
        assert "front matter" in prompt.lower()

    def test_add_example_instruction_mentions_example(self):
        prompt = build_refinement_prompt("existing docs", "add example", "")
        assert "example" in prompt.lower()

    def test_existing_content_included_in_prompt(self):
        prompt = build_refinement_prompt("## My Existing Section", "fix", "typo")
        assert "## My Existing Section" in prompt


# call_llm

class TestCallLlm:
    def _make_client(self, content: str):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_groq_response(content)
        return client

    def test_returns_parsed_dict_on_success(self):
        client = self._make_client(VALID_RESPONSE)
        result = call_llm(client, "prompt")
        assert result["reply"] == "Expanded the CLI Flags section."

    def test_strips_json_fence(self):
        client = self._make_client(FENCED_RESPONSE)
        result = call_llm(client, "prompt")
        assert "updated_markdown" in result

    def test_handles_literal_newlines(self):
        client = self._make_client(LITERAL_NEWLINE_RESPONSE)
        result = call_llm(client, "prompt")
        assert "line1" in result["updated_markdown"]

    @patch("refinement.handler.time.sleep")
    def test_retries_on_failure_then_succeeds(self, mock_sleep):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            Exception("timeout"),
            _make_groq_response(VALID_RESPONSE),
        ]
        result = call_llm(client, "prompt", retries=3)
        assert "updated_markdown" in result
        assert client.chat.completions.create.call_count == 2

    @patch("refinement.handler.time.sleep")
    def test_raises_after_all_retries(self, mock_sleep):
        client = MagicMock()
        client.chat.completions.create.side_effect = Exception("fail")
        with pytest.raises(Exception, match="fail"):
            call_llm(client, "prompt", retries=2)
        assert client.chat.completions.create.call_count == 2
