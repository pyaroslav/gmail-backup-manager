"""
OAuth2 endpoints for Gmail re-authentication from the frontend.

Implements the server-side web OAuth2 flow:
  1. GET /url        -> returns Google authorization URL
  2. GET /callback   -> handles Google redirect, exchanges code for tokens
  3. GET /status     -> returns current token status
"""

import os
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]

REDIRECT_URI = os.getenv(
    "GOOGLE_OAUTH_REDIRECT_URI",
    "http://localhost:8000/api/v1/auth/google/callback",
)


def _build_flow() -> Flow:
    """Create a google_auth_oauthlib Flow for the web-server flow."""
    client_id = os.getenv("GMAIL_CLIENT_ID", "")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError(
            "GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET environment variables must be set"
        )

    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "project_id": "gmail-backup-manager",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": [REDIRECT_URI],
        }
    }

    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = REDIRECT_URI
    return flow


# --------------------------------------------------------------------------- #
# GET /url — generate the Google authorization URL
# --------------------------------------------------------------------------- #
@router.get("/url")
async def get_auth_url():
    try:
        flow = _build_flow()
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return {"url": authorization_url, "state": state}
    except Exception as e:
        logger.error(f"Error generating auth URL: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


# --------------------------------------------------------------------------- #
# GET /callback — Google redirects here after user consent
# --------------------------------------------------------------------------- #
@router.get("/callback")
async def oauth_callback(code: str, state: str = "", db: Session = Depends(get_db)):
    try:
        flow = _build_flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Resolve the authenticated email address
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        service = build("gmail", "v1", credentials=credentials)
        profile = service.users().getProfile(userId="me").execute()
        email = profile["emailAddress"]

        # Upsert user row
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email)
            db.add(user)

        user.gmail_access_token = credentials.token
        user.gmail_refresh_token = credentials.refresh_token
        user.gmail_token_expiry = credentials.expiry
        db.commit()

        logger.info(f"OAuth tokens updated for {email}")

        # Return a small HTML page that notifies the opener and closes itself
        html = f"""<!DOCTYPE html>
<html>
<head><title>Authentication Successful</title></head>
<body style="display:flex;align-items:center;justify-content:center;height:100vh;
             font-family:system-ui,sans-serif;background:#f0fdf4;">
  <div style="text-align:center;">
    <h1 style="color:#16a34a;">Authentication Successful!</h1>
    <p>Gmail account <strong>{email}</strong> has been linked.</p>
    <p style="color:#666;">This window will close automatically&hellip;</p>
  </div>
  <script>
    if (window.opener) {{
      window.opener.postMessage('gmail-auth-success', '*');
    }}
    setTimeout(function() {{ window.close(); }}, 2000);
  </script>
</body>
</html>"""
        return HTMLResponse(content=html)

    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        error_html = f"""<!DOCTYPE html>
<html>
<head><title>Authentication Failed</title></head>
<body style="display:flex;align-items:center;justify-content:center;height:100vh;
             font-family:system-ui,sans-serif;background:#fef2f2;">
  <div style="text-align:center;">
    <h1 style="color:#dc2626;">Authentication Failed</h1>
    <p>{str(e)}</p>
    <p style="color:#666;">You may close this window and try again.</p>
  </div>
</body>
</html>"""
        return HTMLResponse(content=error_html, status_code=500)


# --------------------------------------------------------------------------- #
# GET /status — current token status for the UI
# --------------------------------------------------------------------------- #
@router.get("/status")
async def auth_status(db: Session = Depends(get_db)):
    user = db.query(User).filter(User.is_active.is_(True)).first()
    if not user:
        return {
            "authenticated": False,
            "email": None,
            "token_expiry": None,
            "token_expired": True,
        }

    now = datetime.now(timezone.utc)
    token_expired = True
    token_expiry_str = None

    if user.gmail_token_expiry:
        token_expiry_str = user.gmail_token_expiry.isoformat()
        token_expired = user.gmail_token_expiry < now

    authenticated = bool(user.gmail_refresh_token) and not token_expired

    return {
        "authenticated": authenticated,
        "email": user.email,
        "token_expiry": token_expiry_str,
        "token_expired": token_expired,
    }
