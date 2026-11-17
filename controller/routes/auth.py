from datetime import datetime, timedelta, timezone

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from controller.auth import (
    ALLOWED_EMAILS,
    GOOGLE_AUTH_URL,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_TOKEN_URL,
    GOOGLE_USERINFO_URL,
    SESSION_COOKIE,
    SESSION_SECRET,
)

router = APIRouter()



@router.get("/auth/login")
def auth_login(request: Request):
    redirect_uri = str(request.base_url).rstrip("/") + "/auth/callback"
    params = "&".join([
        f"client_id={GOOGLE_CLIENT_ID}",
        f"redirect_uri={redirect_uri}",
        "response_type=code",
        "scope=openid%20email%20profile",
        "access_type=offline",
        "prompt=select_account",
    ])
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{params}")


@router.get("/auth/callback")
async def auth_callback(code: str, request: Request):
    redirect_uri = str(request.base_url).rstrip("/") + "/auth/callback"
    async with httpx.AsyncClient() as client:
        token_res = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        tokens = token_res.json()
        if "access_token" not in tokens:
            raise HTTPException(status_code=400, detail="OAuth token exchange failed")

        userinfo_res = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        userinfo = userinfo_res.json()

    email = userinfo.get("email", "")
    if userinfo.get("email_verified") is not True or email not in ALLOWED_EMAILS:
        raise HTTPException(status_code=403, detail=f"Access denied for {email}")

    session_token = jwt.encode({
        "email": email,
        "name": userinfo.get("name", email),
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
    }, SESSION_SECRET, algorithm="HS256")

    response = RedirectResponse(url="/")
    response.set_cookie(
        SESSION_COOKIE, session_token,
        httponly=True, samesite="lax",
        max_age=30 * 24 * 3600,
    )
    return response


@router.get("/auth/logout")
def auth_logout():
    response = RedirectResponse(url="/auth/login")
    response.delete_cookie(SESSION_COOKIE)
    return response
