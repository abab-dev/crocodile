import asyncio
from celery import Celery
from core.config import settings
from services.github_service import GitHubService
from services.review_service import generate_review_for_pr

celery_app = Celery(
    "worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL, include=["worker"]
)


@celery_app.task
def review_pull_request_task(installation_id: int, repo_full_name: str, pr_number: int):
    print(f"--- Starting review for PR #{pr_number} in {repo_full_name} ---")
    try:
        review_result = asyncio.run(
            orchestrate_review(installation_id, repo_full_name, pr_number)
        )
        print(f"--- Finished review for PR #{pr_number} in {repo_full_name} ---")
        return review_result
    except Exception as e:
        print(f"!!! ERROR during review for PR #{pr_number}: {e}")
        return f"Failed to review {repo_full_name}#{pr_number}. Error: {e}"


async def orchestrate_review(installation_id: int, repo_full_name: str, pr_number: int):
    github_service = GitHubService(installation_id=installation_id)

    pr_details_task = github_service.get_pr_details(repo_full_name, pr_number)
    pr_diff_task = github_service.get_pr_diff(repo_full_name, pr_number)
    pr_details, pr_diff = await asyncio.gather(pr_details_task, pr_diff_task)

    ai_review = await generate_review_for_pr(
        pr_title=pr_details["title"], pr_body=pr_details["body"], diff=pr_diff
    )

    summary = ai_review.get("summary", "Could not generate a summary.")
    ai_comments = ai_review.get("comments", [])

    print(f"DEBUG: Received {len(ai_comments)} comments from AI")
    print(f"DEBUG: AI comments: {ai_comments}")

    review_comments = []
    for comment in ai_comments:
        if hasattr(comment, "dict"):
            comment_dict = comment.dict()
        elif hasattr(comment, "model_dump"):
            comment_dict = comment.model_dump()
        else:
            comment_dict = comment

        review_comments.append(
            {
                "path": comment_dict.get("path"),
                "line": comment_dict.get("line"),
                "side": comment_dict.get("side", "RIGHT"),
                "body": comment_dict.get("body"),
            }
        )

    print(f"DEBUG: Formatted {len(review_comments)} comments for GitHub")
    print(f"DEBUG: Review comments to post: {review_comments}")

    await github_service.post_review(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        review_summary=f"### 🤖 AI Review Summary\n\n{summary}",
        review_comments=review_comments,
    )

    return "Review posted successfully."
