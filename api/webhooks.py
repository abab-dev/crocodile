import hmac
import hashlib
from fastapi import APIRouter, Request, Header, HTTPException, Depends, Response, status

from core.config import settings
from schemas.github import PullRequestEvent

router = APIRouter()


async def verify_signature(request: Request, x_hub_signature_256: str = Header(...)):
    payload_body = await request.body()
    secret = settings.GITHUB_WEBHOOK_SECRET.encode("utf-8")

    expected_signature = (
        "sha256=" + hmac.new(secret, payload_body, hashlib.sha256).hexdigest()
    )

    if not hmac.compare_digest(expected_signature, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")


@router.post("/webhooks/github", dependencies=[Depends(verify_signature)])
async def post_github_webhook(
    request: Request, payload: PullRequestEvent, x_github_event: str = Header(...)
):
    print(f"Received GitHub Event: '{x_github_event}'")

    if x_github_event == "pull_request":
        print(f"Handling pull_request event for PR #{payload.pull_request.number}")
        print(f"Action: {payload.action}")
        print(f"Repository: {payload.repository.full_name}")
        print(f"Installation ID: {payload.installation.id}")

        if payload.action in ["opened", "synchronize", "reopened"]:
            print("Action is eligible for a review.")

    else:
        print(f"Ignoring event '{x_github_event}' as it is not handled.")

    return Response(status_code=status.HTTP_200_OK)
