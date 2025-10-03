from pydantic import BaseModel, Field
from typing import List


class ReviewComment(BaseModel):
    path: str = Field(
        description="The relative path to the file being commented on (e.g., 'src/main.py')"
    )
    line: int = Field(description="The line number in the NEW version of the file")
    side: str = Field(
        default="RIGHT", description="Either 'LEFT' (old code) or 'RIGHT' (new code)"
    )
    body: str = Field(description="The comment text providing constructive feedback")


class AIGeneratedReview(BaseModel):
    summary: str = Field(description="A high-level summary of the pull request review")
    comments: List[ReviewComment] = Field(
        default_factory=list, description="Line-by-line review comments"
    )
