import time
import jwt
import httpx
from functools import lru_cache
from typing import Dict, Any
from datetime import datetime, timezone

from core.config import settings


@lru_cache
def get_private_key() -> bytes:
    try:
        with open(settings.GITHUB_PRIVATE_KEY_PATH, "rb") as key_file:
            return key_file.read()
    except FileNotFoundError:
        raise RuntimeError(
            f"Private key file not found at: {settings.GITHUB_PRIVATE_KEY_PATH}. "
            "Please check your GITHUB_PRIVATE_KEY_PATH in the .env file."
        )


def generate_jwt_token() -> str:
    now = datetime.now(timezone.utc)
    current_time = int(now.timestamp())

    expiration_time = current_time + 540

    payload = {
        "iat": current_time - 60,
        "exp": expiration_time,
        "iss": settings.GITHUB_APP_ID,
    }

    private_key = get_private_key()
    token = jwt.encode(payload, private_key, algorithm="RS256")

    print(
        f"JWT generated - IAT: {current_time - 60}, EXP: {expiration_time}, Duration: {expiration_time - (current_time - 60)}s"
    )

    return token


async def get_installation_access_token(installation_id: int) -> str:
    app_jwt = generate_jwt_token()

    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers)
            response.raise_for_status()

            response_data = response.json()
            access_token = response_data.get("token")

            if not access_token:
                raise ValueError(
                    "Installation access token not found in GitHub API response."
                )

            return access_token

        except httpx.HTTPStatusError as e:
            print(
                f"Error getting installation token: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            raise


class GitHubService:
    def __init__(self, installation_id: int):
        self.installation_id = installation_id
        self._token = None
        self._headers = None

    async def _authenticate(self):
        if not self._token:
            self._token = await get_installation_access_token(self.installation_id)
            self._headers = {
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github.v3+json",
            }

    async def get_pr_details(
        self, repo_full_name: str, pr_number: int
    ) -> Dict[str, Any]:
        await self._authenticate()
        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._headers)
            response.raise_for_status()
            pr_data = response.json()
            return {
                "title": pr_data.get("title", ""),
                "body": pr_data.get("body", "") or "No description provided.",
            }

    async def get_pr_diff(self, repo_full_name: str, pr_number: int) -> str:
        await self._authenticate()
        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"

        diff_headers = self._headers.copy()
        diff_headers["Accept"] = "application/vnd.github.v3.diff"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=diff_headers)
            response.raise_for_status()
            return response.text

    async def post_review(
        self,
        repo_full_name: str,
        pr_number: int,
        review_summary: str,
        review_comments: list,
    ):
        await self._authenticate()
        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews"

        details_url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
        async with httpx.AsyncClient() as client:
            pr_response = await client.get(details_url, headers=self._headers)
            pr_response.raise_for_status()
            head_sha = pr_response.json()["head"]["sha"]

        print(f"Processing {len(review_comments)} comments from AI response")

        valid_comments = []
        for i, comment in enumerate(review_comments):
            if not isinstance(comment, dict):
                print(f"Skipping non-dict comment at index {i}: {comment}")
                continue

            if "path" not in comment or "body" not in comment:
                print(f"Skipping comment without path or body: {comment}")
                continue

            if "side" not in comment:
                comment["side"] = "RIGHT"

            if "line" not in comment or not isinstance(comment["line"], int):
                print(f"Skipping comment without valid line number: {comment}")
                continue

            valid_comments.append(
                {
                    "path": comment["path"],
                    "line": comment["line"],
                    "side": comment["side"],
                    "body": comment["body"],
                }
            )

        # If no valid comments but there were comments in the response, add debugging
        if len(review_comments) > 0 and len(valid_comments) == 0:
            print(
                "WARNING: All comments were filtered out. This might indicate a formatting issue."
            )
            print(
                "Sample comment from AI:",
                review_comments[0] if review_comments else "None",
            )

        review_payload = {
            "commit_id": head_sha,
            "body": review_summary,
            "event": "COMMENT",
        }

        if valid_comments:
            review_payload["comments"] = valid_comments
            print(f"Posting review with {len(valid_comments)} comments")
            print(f"Sample comment: {valid_comments[0]}")
        else:
            print("No valid line comments. Posting summary-only review.")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, json=review_payload, headers=self._headers
            )

            if response.status_code == 422:
                error_details = response.json()
                print("=" * 60)
                print("GitHub API 422 Error Details:")
                print(f"Error: {error_details}")
                print(f"Payload sent: {review_payload}")
                print("=" * 60)

            response.raise_for_status()
            print(f"Successfully posted review to {repo_full_name}#{pr_number}")
            return response.json()
