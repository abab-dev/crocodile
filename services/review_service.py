from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from core.config import settings
from schemas.review import AIGeneratedReview
from utils.diff_parser import DiffParser


PROMPT_TEMPLATE = """
You are an expert code reviewer for a professional software engineering team.
Your goal is to provide a helpful and constructive review of the following pull request.

**Pull Request Title:**
{pr_title}

**Pull Request Body:**
{pr_body}

**Added/Modified Lines (THESE ARE THE ONLY LINES YOU CAN COMMENT ON):**
{commentable_lines}

**CRITICAL INSTRUCTIONS:**
- Provide a concise, high-level summary of the PR (2-4 sentences).
- Generate 3-5 specific line-by-line comments for the code shown above.
-  IMPORTANT: You can ONLY comment on line numbers that appear in the "Added/Modified Lines" section above.
- DO NOT invent line numbers. DO NOT comment on lines not shown above.
- For each comment, you MUST specify:
  * `path`: The file path (EXACTLY as shown above, e.g., "packages/whatsapp/src/schemas.ts")
  * `line`: The EXACT line number shown above (must match one of the line numbers you see)
  * `side`: Always use "RIGHT"
  * `body`: Your constructive feedback (2-4 sentences, be specific and helpful)

**What to look for:**
- Potential bugs or edge cases
- Security vulnerabilities  
- Performance concerns
- Code readability improvements
- Missing error handling
- Best practices violations
- Better variable/function naming
- Opportunities for code simplification
- Missing documentation for complex logic
- Type safety issues
- Inconsistent patterns

**CRITICAL:** Before including a comment, double-check that the line number actually appears in the "Added/Modified Lines" section. If you're not 100% certain, skip that comment.

**JSON Output Format:**
{format_instructions}

Example of CORRECT comment:
{{
  "path": "src/main.py",
  "line": 42,
  "side": "RIGHT",
  "body": "Consider adding null checking here to prevent potential runtime errors if the user object is undefined."
}}

REMEMBER: Only use line numbers that appear in the Added/Modified Lines list above!
"""


def get_review_chain():
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.3,
        convert_system_message_to_human=True,
    )
    parser = JsonOutputParser(pydantic_object=AIGeneratedReview)
    prompt = ChatPromptTemplate.from_template(
        template=PROMPT_TEMPLATE,
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    chain = prompt | llm | parser
    return chain


review_chain = get_review_chain()


async def generate_review_for_pr(pr_title: str, pr_body: str, diff: str) -> dict:
    print("\n🤖 Generating AI review...")

    diff_parser = DiffParser(diff)
    commentable_context = diff_parser.get_added_lines_context()

    if (
        not commentable_context.strip()
        or commentable_context == "No added lines found in diff."
    ):
        print("  No added lines found in diff - nothing to review")
        return {
            "summary": "This PR contains no added code lines to review (only deletions or file renames).",
            "comments": [],
        }

    total_files = len(diff_parser.get_all_files())
    total_lines = sum(
        len(diff_parser.get_commentable_lines(f)) for f in diff_parser.get_all_files()
    )

    print(f" Diff Statistics:")
    print(f"   • Total diff size: {len(diff):,} characters")
    print(f"   • Files modified: {total_files}")
    print(f"   • Added lines: {total_lines}")

    print(f"\n Sending commentable lines to AI (preview):")
    preview = commentable_context[:400]
    print(preview + "..." if len(commentable_context) > 400 else preview)

    try:
        response = await review_chain.ainvoke(
            {
                "pr_title": pr_title,
                "pr_body": pr_body or "No description provided.",
                "commentable_lines": commentable_context,
            }
        )
    except Exception as e:
        print(f" Error generating AI review: {e}")
        return {
            "summary": "Failed to generate AI review due to an error.",
            "comments": [],
        }

    print("\n AI review generated successfully")
    print("=" * 60)
    summary = response.get("summary", "N/A")
    print(f" Summary: {summary[:150]}{'...' if len(summary) > 150 else ''}")

    comments = response.get("comments", [])
    if comments:
        print(f"\nGenerated {len(comments)} comments:")
        for i, comment in enumerate(comments[:5], 1):
            path = comment.get("path", "N/A")
            line = comment.get("line", "N/A")
            body = comment.get("body", "")
            preview_body = body[:60] + "..." if len(body) > 60 else body
            print(f"   {i}. {path}:{line} - {preview_body}")

        if len(comments) > 5:
            print(f"   ... and {len(comments) - 5} more")
    else:
        print("\n  No specific comments generated by AI")

    print("=" * 60)
    return response
