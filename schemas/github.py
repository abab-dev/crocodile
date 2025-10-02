from pydantic import BaseModel, Field
from typing import Optional, Dict


class User(BaseModel):
    login: str


class Repository(BaseModel):
    full_name: str


class Installation(BaseModel):
    id: int


class PullRequest(BaseModel):
    number: int
    title: str
    user: User


class PullRequestEvent(BaseModel):
    action: str
    pull_request: PullRequest = Field(..., alias="pull_request")
    repository: Repository
    installation: Installation

    class Config:
        extra = "allow"
