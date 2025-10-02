import hmac
import hashlib
from fastapi import APIRouter, Request, Header, HTTPException, Depends, Response, status

from core.config import settings
from schemas.github import PullRequestEvent
from worker import review_pull_request_task

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
    payload: PullRequestEvent, x_github_event: str = Header(...)
):
    if x_github_event == "pull_request":
        repo_full_name = payload.repository.full_name
        pr_number = payload.pull_request.number

        if payload.action in ["opened", "synchronize", "reopened"]:
            print(f"Queuing review for PR #{pr_number} in {repo_full_name}")

            review_pull_request_task.delay(
                installation_id=payload.installation.id,
                repo_full_name=repo_full_name,
                pr_number=pr_number,
            )
            return {"message": "Review task queued successfully."}

    return Response(status_code=status.HTTP_204_NO_CONTENT)
