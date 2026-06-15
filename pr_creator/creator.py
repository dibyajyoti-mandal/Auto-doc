import json
import os
from pathlib import Path

from github import Github, GithubException

GENERATED_DOCS_PATH = "generated_docs.json"
METADATA_PATH = "metadata.json"
WEBSITE_REPO = "dibyajyoti-mandal/website"
LABEL = "auto-docs"


def _build_pr_body(metadata: dict, summary: str, modified_sections: list[str]) -> str:
    repo = metadata["repo"]
    pr_number = metadata["pr_number"]
    pr_title = metadata["pr_title"]

    sections = "\n".join(f"- {s}" for s in modified_sections)

    return f"""## Automated Documentation Update

**Triggered by:** {repo}#{pr_number} — _{pr_title}_

### What changed
{summary}

### Modified sections
{sections}

### Reviewer checklist
- [ ] Front matter is correct
- [ ] CLI flag table is accurate
- [ ] No hallucinated values
- [ ] Content reads naturally

---
> This PR was opened automatically by the docs-sync bot.
> Use `@krkn-docs-bot` commands to refine the content (coming in Phase 5).
"""


def _ensure_label_exists(repo):
    try:
        repo.get_label(LABEL)
    except GithubException:
        repo.create_label(LABEL, "0075ca")


def run():
    # 1. Load inputs
    with open(METADATA_PATH) as f:
        metadata = json.load(f)

    with open(GENERATED_DOCS_PATH) as f:
        generated = json.load(f)

    token = os.environ["BOT_TOKEN"]
    gh = Github(token)
    website = gh.get_repo(WEBSITE_REPO)

    _ensure_label_exists(website)

    repo_short = metadata["repo"].split("/")[-1]   # "krknctl"
    pr_number = metadata["pr_number"]
    upstream_ref = f"{metadata['repo']}#{pr_number}"
    branch_name = f"docs/sync/{repo_short}-pr-{pr_number}"

    # 2. Idempotency check — don't open duplicate PRs
    for existing_pr in website.get_pulls(state="open"):
        if upstream_ref in (existing_pr.body or ""):
            print(f"Draft PR already exists: {existing_pr.html_url}. Updating branch instead.")
            _update_files(website, existing_pr.head.ref, generated)
            return

    # 3. Create branch from main
    main_sha = website.get_branch("main").commit.sha
    try:
        website.create_git_ref(f"refs/heads/{branch_name}", main_sha)
        print(f"Created branch: {branch_name}")
    except GithubException as e:
        if "already exists" in str(e):
            print(f"Branch {branch_name} already exists, reusing.")
        else:
            raise

    # 4. Write generated files to branch
    _update_files(website, branch_name, generated)

    # 5. Build PR body from first generated doc
    first = generated[0]
    summary = first.get("pr_summary", "Automated documentation update.")
    modified_sections = first.get("modified_sections", [])
    pr_body = _build_pr_body(metadata, summary, modified_sections)

    # 6. Open draft PR
    pr = website.create_pull(
        title=f"docs(auto): {metadata['pr_title']}",
        body=pr_body,
        head=branch_name,
        base="main",
        draft=True,
    )
    pr.add_to_labels(LABEL)
    print(f"Draft PR opened: {pr.html_url}")


def _update_files(repo, branch: str, generated: list[dict]):
    for doc in generated:
        path = doc["target_page"]
        content = doc["updated_markdown"]

        try:
            existing = repo.get_contents(path, ref=branch)
            repo.update_file(
                path=path,
                message=f"docs(auto): update {path}",
                content=content,
                sha=existing.sha,
                branch=branch,
            )
            print(f"Updated: {path}")
        except GithubException as e:
            if e.status == 404:
                repo.create_file(
                    path=path,
                    message=f"docs(auto): create {path}",
                    content=content,
                    branch=branch,
                )
                print(f"Created: {path}")
            else:
                raise


if __name__ == "__main__":
    run()