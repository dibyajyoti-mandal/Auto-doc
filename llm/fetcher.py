import base64
import requests


def fetch_target_page(path: str, token: str, repo: str) -> str:
    """
    Fetch the current content of a file from the website repo.
    Returns empty string if the file doesn't exist yet.
    """
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 404:
        print(f"Target page {path} does not exist yet. Will create from scratch.")
        return ""

    response.raise_for_status()
    content_b64 = response.json()["content"]
    return base64.b64decode(content_b64).decode("utf-8")