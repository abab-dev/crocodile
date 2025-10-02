from pydantic import BaseModel, Field
from typing import List


class ReviewComment(BaseModel):
    line_number: int = Field(..., description="The line number the comment applies to.")
    comment: str = Field(..., description="The constructive feedback or comment.")


class AIGeneratedReview(BaseModel):
    summary: str = Field(
        ...,
        description="A brief, high-level summary of the pull request's purpose and quality.",
    )
    comments: List[ReviewComment] = Field(
        default_factory=list,
        description="A list of specific, line-by-line comments for code improvement.",
    )
