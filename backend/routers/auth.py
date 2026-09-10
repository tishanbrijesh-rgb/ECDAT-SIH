"""Local signed-session endpoint used for the SIH demonstration."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, StrictStr, field_validator

from backend.security import current_role, issue_demo_token
from backend.middleware.rate_limit import limit as rate_limit

router = APIRouter(prefix="/api/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    username: StrictStr = Field(min_length=1, max_length=128)
    password: StrictStr = Field(min_length=1, max_length=1024)

    @field_validator("username", "password")
    @classmethod
    def valid_unicode(cls, value: str) -> str:
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise ValueError("Credentials must contain valid Unicode") from None
        return value


@router.post("/login")
@rate_limit(threshold=5, window=60)
def login(request: Request, payload: LoginRequest) -> dict[str, str | int]:
    return issue_demo_token(payload.username, payload.password)


@router.get("/me")
def me(role: str = Depends(current_role)) -> dict[str, str]:
    return {"role": role, "authentication": "signed-session"}
