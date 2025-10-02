from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from core.config import settings
from schemas.review import AIGeneratedReview

PROMPT_TEMPLATE = """
You are an expert code reviewer for a professional software engineering team.
Your goal is to provide a helpful and constructive review of the following pull request.

Please analyze the provided pull request diff and generate a high-level summary
and specific, line-by-line comments where you see opportunities for improvement.
Focus on code quality, potential bugs, best practices, and maintainability.
Do not comment on trivial style issues that a linter would catch.

**Pull Request Title:**
{pr_title}

**Pull Request Body:**
{pr_body}

**Code Diff:**
```diff
{diff}
```

**Instructions:**
- Provide a concise, high-level summary of the PR.
- If you have specific feedback, provide comments on individual lines.
- For each comment, specify the exact line number from the diff.
- If there are no specific issues, return an empty list for the comments.
- Your entire response must be in the JSON format specified below.

**JSON Output Format:**
{format_instructions}
"""


def get_review_chain():
    """
    Initializes and returns a LangChain chain for code reviews.

    The chain is composed of:
    1. A Google Gemini chat model.
    2. A Pydantic JSON parser to structure the output.
    3. A prompt template that combines the PR data with formatting instructions.
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.2,
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
    """
    Asynchronously generates a structured code review for a given PR's context.

    Args:
        pr_title: The title of the pull request.
        pr_body: The description/body of the pull request.
        diff: The unified diff string of the changes.

    Returns:
        A dictionary matching the AIGeneratedReview schema.
    """
    print("Generating AI review...")
    response = await review_chain.ainvoke(
        {
            "pr_title": pr_title,
            "pr_body": pr_body,
            "diff": diff,
        }
    )
    print("AI review generated successfully.")
    return response
