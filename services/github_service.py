import time
import jwt
import httpx
from functools import lru_cache

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
