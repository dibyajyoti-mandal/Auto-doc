import json
import os
import time
from pathlib import Path

import anthropic

from generator.fetcher import fetch_target_page


WEBSITE_REPO = "dibyajyoti-mandal/website"
OUTPUT_PATH = "generated_docs.json"
PAYLOAD_PATH = "change_payload.json"


SYSTEM_PROMPT = """You are an automated documentation bot for the krkn-chaos project.
Your job is to update Hugo/Docsy markdown documentation pages based on code changes.

Rules you must follow:
- Preserve the existing front matter (the --- block) exactly as-is
- Only update the sections relevant to the changes described in the task
- Leave all other content untouched
- CLI flag tables must use this exact format:
  | Flag | Type | Default | Description |
  |------|------|---------|-------------|
- Do not hallucinate parameter names, types, or default values — use only what is in the task block
- Your entire response must be a single valid JSON object with no preamble, no markdown fences

Output this exact JSON structure:
{
  "updated_markdown": "<full updated page content>",
  "pr_summary": "<one paragraph describing what changed>",
  "modified_sections": ["<section name>", ...]
}"""


def build_user_prompt(existing_content: str, payload: dict) -> str:
    return f"""## Existing page content

{existing_content if existing_content else "This is a new page. Create it from scratch using the task block below."}

## Task

The following code changes were detected in {payload['repo']} (PR #{payload['pr_number']}): "{payload['pr_title']}"

{json.dumps(payload['changes'], indent=2)}

Update the documentation page above to reflect these changes.
Return only the JSON object described in your instructions."""


def call_llm_with_retry(client: anthropic.Anthropic, user_prompt: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            response = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
        except Exception as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"LLM call failed (attempt {attempt + 1}): {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise


def main():
    # 1. Load change payload
    with open(PAYLOAD_PATH) as f:
        payload = json.load(f)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    bot_token = os.environ["BOT_TOKEN"]

    all_generated = []

    for change in payload["changes"]:
        target_page = change["target_page"]
        print(f"Processing change for target page: {target_page}")

        # 2. Fetch existing page content
        existing_content = fetch_target_page(target_page, bot_token, WEBSITE_REPO)

        # 3. Build prompt
        user_prompt = build_user_prompt(existing_content, {
            "repo": payload["repo"],
            "pr_number": payload["pr_number"],
            "pr_title": payload["pr_title"],
            "changes": [change],
        })

        # 4. Call LLM
        print(f"Calling LLM for {target_page}...")
        raw_response = call_llm_with_retry(client, user_prompt)

        # 5. Parse response
        try:
            result = json.loads(raw_response)
        except json.JSONDecodeError:
            # strip accidental markdown fences if present
            cleaned = raw_response.strip().removeprefix("```json").removesuffix("```").strip()
            result = json.loads(cleaned)

        result["target_page"] = target_page
        all_generated.append(result)
        print(f"Done. Modified sections: {result.get('modified_sections', [])}")

    # 6. Write output
    with open(OUTPUT_PATH, "w") as f:
        json.dump(all_generated, f, indent=2)

    print(f"generated_docs.json written with {len(all_generated)} page(s).")


if __name__ == "__main__":
    main()