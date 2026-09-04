"""Signed demo sessions, RBAC, and audit helpers for the local SIH deployment."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Header, HTTPException
from backend.db import SessionLocal
from backend.models.audit_log import AuditLogDB

ROLES = {"admin", "security_analyst", "auditor", "viewer"}
DEMO_USERS = {
    "admin": "admin",
    "analyst": "security_analyst",
    "auditor": "auditor",
    "viewer": "viewer",
}


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_demo_token(username: str, password: str) -> dict[str, str | int]:
    """Issue a short-lived HMAC session for one documented local demo account."""
    role = DEMO_USERS.get(username.lower())
    expected = os.getenv("ECDAT_DEMO_PASSWORD", "ecdat-demo")
    if role is None or not hmac.compare_digest(password, expected):
        raise HTTPException(401, "Invalid demo credentials")
    expires_at = int(time.time()) + int(os.getenv("ECDAT_TOKEN_TTL_SECONDS", "28800"))
    payload = _encode(json.dumps({"sub": username.lower(), "role": role, "exp": expires_at}, separators=(",", ":")).encode())
    secret = os.getenv("ECDAT_TOKEN_SECRET", "change-this-secret-before-deployment").encode()
    signature = _encode(hmac.new(secret, payload.encode(), hashlib.sha256).digest())
    return {"access_token": f"{payload}.{signature}", "token_type": "bearer", "role": role, "expires_at": expires_at}


def role_from_token(token: str) -> str:
    try:
        payload, signature = token.split(".", 1)
        secret = os.getenv("ECDAT_TOKEN_SECRET", "change-this-secret-before-deployment").encode()
        expected = _encode(hmac.new(secret, payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        claims = json.loads(_decode(payload))
        if int(claims["exp"]) < int(time.time()) or claims["role"] not in ROLES:
            raise ValueError("expired or invalid role")
        return str(claims["role"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(401, "Invalid or expired ECDAT session") from exc


def current_role(
    authorization: str | None = Header(default=None),
    x_ecdat_role: str | None = Header(default=None),
) -> str:
    """Resolve a signed session, with an explicitly configurable demo-header fallback."""
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(401, "Use Authorization: Bearer <token>")
        return role_from_token(token)
    allow_header = os.getenv("ECDAT_ALLOW_ROLE_HEADER", "true").lower() == "true"
    if not allow_header:
        raise HTTPException(401, "Authentication required")
    role = (x_ecdat_role or "security_analyst").lower().replace(" ", "_")
    if role not in ROLES:
        raise HTTPException(403, "Unknown ECDAT role")
    return role

def ensure_write_role(role: str) -> None:
    if role not in {"admin", "security_analyst"}:
        raise HTTPException(403, "This action requires Admin or Security Analyst role")

def record_audit(action: str, resource: str, role: str = "security_analyst", details: dict | None = None) -> None:
    db = SessionLocal()
    try:
        db.add(AuditLogDB(actor_role=role, action=action, resource=resource, details=details or {})); db.commit()
    finally: db.close()
