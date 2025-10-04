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
    return asyncio.run(orchestrate_review(installation_id, repo_full_name, pr_number))


async def orchestrate_review(installation_id: int, repo_full_name: str, pr_number: int):
    try:
        print(f"--- Starting review for PR #{pr_number} in {repo_full_name} ---")

        github_service = GitHubService(installation_id=installation_id)

        print(" Fetching PR details and diff...")
        pr_details_task = github_service.get_pr_details(repo_full_name, pr_number)
        pr_diff_task = github_service.get_pr_diff(repo_full_name, pr_number)
        pr_details, pr_diff = await asyncio.gather(pr_details_task, pr_diff_task)

        pr_title = pr_details["title"]
        pr_body = pr_details["body"]

        print(f" PR Title: {pr_title}")
        print(f" Diff size: {len(pr_diff)} characters")

        print("🤖 Generating AI review...")
        ai_review = await generate_review_for_pr(
            pr_title=pr_title, pr_body=pr_body, diff=pr_diff
        )

        summary = ai_review.get("summary", "Could not generate a summary.")
        ai_comments = ai_review.get("comments", [])

        print(f"AI Review Results:")
        print(f"   - Summary: {summary[:100]}...")
        print(f"   - Comments generated: {len(ai_comments)}")

        review_comments = []
        for comment in ai_comments:
            if hasattr(comment, "dict"):
                comment_dict = comment.dict()
            elif hasattr(comment, "model_dump"):
                comment_dict = comment.model_dump()
            else:
                comment_dict = comment

            if all(key in comment_dict for key in ["path", "line", "body"]):
                review_comments.append(
                    {
                        "path": comment_dict.get("path"),
                        "line": comment_dict.get("line"),
                        "side": comment_dict.get("side", "RIGHT"),
                        "body": comment_dict.get("body"),
                    }
                )
            else:
                print(f"  Skipping malformed comment: {comment_dict}")

        print(f"✓ Formatted {len(review_comments)} valid comments")

        print(" Posting review to GitHub...")
        await github_service.post_review(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            review_summary=f"### 🤖 AI Review Summary\n\n{summary}",
            review_comments=review_comments,
            diff=pr_diff,
        )

        print(f" Review completed successfully for {repo_full_name}#{pr_number}")
        return f"Successfully reviewed {repo_full_name}#{pr_number}"

    except Exception as e:
        error_msg = f"Failed to review {repo_full_name}#{pr_number}. Error: {str(e)}"
        print(f" ERROR: {error_msg}")
        import traceback

        traceback.print_exc()
        return error_msg
