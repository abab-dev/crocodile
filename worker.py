import asyncio
from celery import Celery

from core.config import settings
from services.github_service import GitHubService
from services.review_service import generate_review_for_pr

celery_app = Celery(
    "worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL, include=["worker"]
)


def format_review_comments(diff: str, ai_review_comments: list) -> list:
    formatted_comments = []
    diff_lines = diff.split("\n")

    for comment in ai_review_comments:
        target_line_number = comment.get("line_number")
        if target_line_number is None:
            continue

        position = 0
        file_line_counter = 0
        for i, line in enumerate(diff_lines):
            if (
                line.startswith("---")
                or line.startswith("+++")
                or line.startswith("@@")
            ):
                continue
            position += 1
            if line.startswith("-"):
                continue

            file_line_counter += 1
            if file_line_counter == target_line_number:
                formatted_comments.append(
                    {
                        "body": comment["comment"],
                        "position": position,
                    }
                )
                break

    return formatted_comments


def find_file_path_from_diff(diff: str) -> str:
    """A simple helper to extract the first file path from a diff."""
    for line in diff.split("\n"):
        if line.startswith("+++ b/"):
            return line[6:]
    return "unknown_file.py"


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

    file_path = find_file_path_from_diff(pr_diff)

    review_comments = []
    diff_lines = pr_diff.split("\n")
    current_file_line = 0
    position_in_diff = 0

    for line in diff_lines:
        position_in_diff += 1
        if line.startswith(("---", "+++", "@@")):
            continue
        if not line.startswith("-"):
            current_file_line += 1

        for comment in ai_comments:
            if comment.get("line_number") == current_file_line:
                review_comments.append(
                    {
                        "path": file_path,
                        "position": position_in_diff,
                        "body": comment["comment"],
                    }
                )

    await github_service.post_review(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        review_summary=f"### 🤖 AI Review Summary\n\n{summary}",
        review_comments=review_comments,
    )

    return "Review posted successfully."
