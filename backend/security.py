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


def _settings():
    """Fail closed; provision distinct account credentials outside source control."""
    try:
        secret = os.environ["ECDAT_TOKEN_SECRET"]
        users = json.loads(os.environ["ECDAT_USERS_JSON"])
        if len(secret) < 32 or secret in {"change-this-secret-before-deployment", "replace-with-a-long-random-secret"}:
            raise ValueError()
        if not isinstance(users, dict) or not users:
            raise ValueError()
        passwords = []
        for name, user in users.items():
            if not isinstance(name, str) or name != name.lower() or not isinstance(user, dict):
                raise ValueError()
            password = user["password"]
            if user["role"] not in ROLES or not isinstance(password, str) or len(password) < 16:
                raise ValueError()
            passwords.append(password)
        if len(set(passwords)) != len(passwords) or secret in passwords:
            raise ValueError()
        return secret.encode(), users
    except (KeyError, ValueError, TypeError):
        raise HTTPException(503, "Authentication configuration is missing or invalid") from None


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_demo_token(username: str, password: str) -> dict[str, str | int]:
    """Issue a short-lived HMAC session for one documented local demo account."""
    secret, users = _settings()
    user = users.get(username.lower())
    expected = user["password"] if user else "invalid-account-password"
    if not hmac.compare_digest(password.encode(), expected.encode()) or user is None:
        raise HTTPException(401, "Invalid demo credentials")
    role = user["role"]
    expires_at = int(time.time()) + 3600
    payload = _encode(json.dumps({"sub": username.lower(), "role": role, "exp": expires_at}, separators=(",", ":")).encode())
    signature = _encode(hmac.new(secret, payload.encode(), hashlib.sha256).digest())
    return {"access_token": f"{payload}.{signature}", "token_type": "bearer", "role": role, "expires_at": expires_at}


def role_from_token(token: str) -> str:
    secret, users = _settings()
    try:
        if len(token) > 4096:
            raise ValueError("oversized")
        payload, signature = token.split(".", 1)
        expected = _encode(hmac.new(secret, payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature.encode(), expected.encode()):
            raise ValueError("signature")
        claims = json.loads(_decode(payload))
        if not isinstance(claims, dict) or type(claims.get("exp")) is not int:
            raise ValueError("claims")
        if claims["exp"] <= int(time.time()) or claims["role"] not in ROLES or users.get(claims["sub"], {}).get("role") != claims["role"]:
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
    allow_header = os.getenv("ECDAT_ALLOW_ROLE_HEADER", "false").lower() == "true"
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
