"""Local signed-session endpoint used for the SIH demonstration."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.security import current_role, issue_demo_token

router = APIRouter(prefix="/api/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(payload: LoginRequest) -> dict[str, str | int]:
    return issue_demo_token(payload.username, payload.password)


@router.get("/me")
def me(role: str = Depends(current_role)) -> dict[str, str]:
    return {"role": role, "authentication": "signed-session"}
