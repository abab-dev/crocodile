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
- Provide a concise, high-level summary of the PR (2-4 sentences).
- If you have specific feedback, provide comments on individual lines.
- For each comment, you MUST specify:
  * `path`: The file path (e.g., "src/main.py") - extract this from the diff headers (lines starting with "+++")
  * `line`: The exact line number in the NEW version of the file (look for line numbers after @@ in the diff)
  * `side`: Use "RIGHT" for commenting on new/added code (lines starting with +)
  * `body`: Your constructive feedback (be specific and helpful)
- Focus ONLY on lines that start with "+" (new code) in the diff.
- If there are no specific issues, return an empty list for the comments.
- Your entire response must be in the JSON format specified below.

**How to extract file paths and line numbers from diffs:**

Example diff:
```
diff --git a/src/utils.py b/src/utils.py
--- a/src/utils.py
+++ b/src/utils.py
@@ -10,5 +12,7 @@ def example():
+    new_line = "test"
```

- File path: "src/utils.py" (from "+++ b/src/utils.py", remove the "b/" prefix)
- Line number: 12 (from "@@ -10,5 +12,7 @@", the "12" is the starting line in the new file)
- For subsequent lines, increment from the starting line number

**JSON Output Format:**
{format_instructions}
"""


def get_review_chain():
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
    print("Generating AI review...")
    response = await review_chain.ainvoke(
        {
            "pr_title": pr_title,
            "pr_body": pr_body,
            "diff": diff,
        }
    )
    print("AI review generated successfully.")
    print("=" * 50)
    print(f"Summary: {response.get('summary', 'N/A')}")
    if "comments" in response and response["comments"]:
        print(f"Generated {len(response['comments'])} comments")
        print("First comment sample:")
        print(f"  Path: {response['comments'][0].get('path')}")
        print(f"  Line: {response['comments'][0].get('line')}")
        print(f"  Body: {response['comments'][0].get('body')[:50]}...")
    else:
        print("No specific comments generated")
    print("=" * 50)
    return response
