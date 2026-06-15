import json
import os
import re
import time
import base64

from groq import Groq
from github import Github, GithubException

WEBSITE_REPO = "dibyajyoti-mandal/website"
LABEL = "auto-docs"

COMMANDS = {
    "expand": r"@krkn-docs-bot expand (.+)",
    "fix": r"@krkn-docs-bot fix (.+)",
    "regenerate": r"@krkn-docs-bot regenerate",
    "add example": r"@krkn-docs-bot add example",
}

SYSTEM_PROMPT = """You are an automated documentation bot for the krkn-chaos project.
You are refining an existing documentation page based on a reviewer's instruction.

Rules:
- Preserve front matter exactly as-is
- Apply only the change the reviewer requested
- Do not touch anything else on the page
- Return a single valid JSON object with no preamble or markdown fences:
{
  "updated_markdown": "<full updated page content>",
  "reply": "<one sentence confirming what you changed>"
}"""


def parse_command(comment: str) -> tuple[str, str]:
    """
    Returns (command_type, argument).
    argument is empty string for commands that take no argument.
    """
    for cmd, pattern in COMMANDS.items():
        match = re.search(pattern, comment, re.IGNORECASE)
        if match:
            arg = match.group(1).strip() if match.lastindex else ""
            return cmd, arg
    return None, None


def build_refinement_prompt(existing_content: str, command: str, argument: str) -> str:
    instruction = {
        "expand": f"Expand the '{argument}' section with more detail.",
        "fix": f"Apply this correction: {argument}",
        "regenerate": "Regenerate the entire page content from scratch, keeping front matter.",
        "add example": "Append a practical usage example to the most relevant section.",
    }.get(command, "")

    return f"""## Current page content

{existing_content}

## Reviewer instruction

{instruction}

Apply the instruction and return the JSON object."""


def call_llm(client: Groq, prompt: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
            )
            raw = response.choices[0].message.content
            try:
                return json.loads(raw, strict=False)
            except json.JSONDecodeError:
                cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                return json.loads(cleaned, strict=False)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise


def run():
    token = os.environ["BOT_TOKEN"]
    comment_body = os.environ["COMMENT_BODY"]
    pr_number = int(os.environ["PR_NUMBER"])
    repo_name = os.environ["REPO"]

    gh = Github(token)
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pr_number)

    # 1. Only act on auto-docs PRs
    label_names = [l.name for l in pr.labels]
    if LABEL not in label_names:
        print("PR is not an auto-docs PR. Skipping.")
        return

    # 2. Parse command
    command, argument = parse_command(comment_body)
    if not command:
        print("No recognized command in comment. Skipping.")
        return

    print(f"Command: {command}, Argument: {argument}")

    # 3. Acknowledge the command
    pr.create_issue_comment(f"⚙️ Processing `{command}` command with argument: `{argument or 'none'}`…")

    # 4. Get the changed files from the PR
    pr_files = list(pr.get_files())
    if not pr_files:
        pr.create_issue_comment("❌ No files found in this PR.")
        return

    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    for pr_file in pr_files:
        path = pr_file.filename

        # 5. Fetch current content from the PR branch
        try:
            file_obj = repo.get_contents(path, ref=pr.head.ref)
            existing_content = base64.b64decode(file_obj.content).decode("utf-8")
        except GithubException:
            pr.create_issue_comment(f"❌ Could not fetch `{path}`.")
            continue

        # 6. Call LLM
        prompt = build_refinement_prompt(existing_content, command, argument)
        result = call_llm(client, prompt)

        updated_markdown = result["updated_markdown"]
        reply = result.get("reply", "Done.")

        # 7. Push updated content to PR branch
        repo.update_file(
            path=path,
            message=f"docs(bot): {command} — {argument or 'refinement'}",
            content=updated_markdown,
            sha=file_obj.sha,
            branch=pr.head.ref,
        )

        print(f"Updated {path} on branch {pr.head.ref}")

    # 8. Reply on the PR
    pr.create_issue_comment(f"✅ {reply}")


if __name__ == "__main__":
    run()