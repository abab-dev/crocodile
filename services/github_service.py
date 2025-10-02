import time
import jwt
import httpx
from functools import lru_cache
from typing import Dict, Any


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
    current_time = int(time.time())

    payload = {
        "iat": current_time,
        "exp": current_time + 600,
        "iss": settings.GITHUB_APP_ID,
    }

    private_key = get_private_key()

    token = jwt.encode(payload, private_key, algorithm="RS256")

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
    """A wrapper class for interacting with the GitHub API on behalf of an installation."""

    def __init__(self, installation_id: int):
        self.installation_id = installation_id
        self._token = None
        self._headers = None

    async def _authenticate(self):
        """Authenticates the service by obtaining an installation access token."""
        if not self._token:
            self._token = await get_installation_access_token(self.installation_id)
            self._headers = {
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github.v3+json",
            }

    async def get_pr_details(
        self, repo_full_name: str, pr_number: int
    ) -> Dict[str, Any]:
        """Fetches the title and body of a pull request."""
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
        """Fetches the diff for a pull request."""
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
        """Posts a review with comments to a pull request."""
        await self._authenticate()
        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews"

        details_url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
        async with httpx.AsyncClient() as client:
            pr_response = await client.get(details_url, headers=self._headers)
            pr_response.raise_for_status()
            head_sha = pr_response.json()["head"]["sha"]

        review_payload = {
            "commit_id": head_sha,
            "body": review_summary,
            "event": "COMMENT",
            "comments": review_comments,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, json=review_payload, headers=self._headers
            )
            response.raise_for_status()
            print(f"Successfully posted review to {repo_full_name}#{pr_number}")
            return response.json()
