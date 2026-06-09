"""
Shared Google OAuth token management for all Google integrations.

Each Gmail account has its own per-account token file (token_gmail_{account_name}.json).
One shared google_credentials.json (the app's OAuth client) is used for all accounts.

Setup:
1. Download OAuth credentials from Google Cloud Console → Desktop app
2. Save as .claude/scripts/integrations/google_credentials.json
3. Run: uv run python integrations/setup_auth.py
   (on headless machines: uv run python integrations/setup_auth.py --headless)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Add parent dir for config imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import GOOGLE_CREDENTIALS_FILE, GOOGLE_SCOPES, google_token_file  # noqa: E402


def get_google_credentials(account_name: str = "personal") -> Any:
    """
    Load Google OAuth credentials for the given account, refreshing if expired.

    Returns authenticated Credentials object usable for Gmail and Calendar APIs.
    Raises FileNotFoundError if credentials file is missing.
    Raises RuntimeError if token is invalid and re-auth is needed.
    """
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    token_file = google_token_file(account_name)
    creds: Credentials | None = None

    # Load existing token
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
            str(token_file), GOOGLE_SCOPES
        )

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_json: str = creds.to_json()  # type: ignore[no-untyped-call]
            token_file.write_text(token_json, encoding="utf-8")
            return creds
        except RefreshError as e:
            raise RuntimeError(
                f"Google token refresh failed for account '{account_name}': {e}\n"
                "Run 'uv run python integrations/setup_auth.py' to re-authenticate."
            ) from e

    # Valid credentials exist
    if creds and creds.valid:
        return creds

    # Need initial auth flow
    raise RuntimeError(
        f"No valid Google OAuth token found for account '{account_name}'.\n"
        "Run 'uv run python integrations/setup_auth.py' to authenticate."
    )


def run_initial_auth(account_name: str = "personal", headless: bool = False) -> Any:
    """
    Run the interactive OAuth flow for one account (one-time setup).

    Args:
        account_name: Which Gmail account to authenticate (e.g. "personal", "sbdb").
        headless: If True, use manual copy-paste flow (no browser needed).
                  If False, opens a browser and runs a local callback server.

    Requires google_credentials.json to be present.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]

    if not GOOGLE_CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"Google credentials file not found: {GOOGLE_CREDENTIALS_FILE}\n"
            "Download from Google Cloud Console → APIs & Services → Credentials → "
            "OAuth 2.0 Client ID → Desktop app → Download JSON"
        )

    print(f"Authenticating account: {account_name}")
    token_file = google_token_file(account_name)

    flow = InstalledAppFlow.from_client_secrets_file(
        str(GOOGLE_CREDENTIALS_FILE), GOOGLE_SCOPES
    )

    if headless:
        flow.redirect_uri = "http://localhost:1"
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

        print("\n" + "=" * 60)
        print(f"  HEADLESS GOOGLE OAUTH SETUP — {account_name}")
        print("=" * 60)
        print(f"\n1. Open this URL in your browser:\n\n{auth_url}\n")
        print("2. Authorize the app and grant all requested permissions.")
        print("3. You'll be redirected to a page that FAILS to load (localhost:1).")
        print("   That's expected! Copy the FULL URL from your browser's address bar.")
        print("   It looks like: http://localhost:1/?state=...&code=...&scope=...")
        print()
        redirect_response = input("4. Paste the full redirect URL here: ").strip()
        flow.fetch_token(authorization_response=redirect_response)
        creds = flow.credentials
    else:
        creds = flow.run_local_server(port=0)

    # Save per-account token
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    print(f"\nToken saved to {token_file}")

    return creds


def is_google_authenticated(account_name: str = "personal") -> bool:
    """Check if a valid Google OAuth token exists for the given account."""
    token_file = google_token_file(account_name)
    if not token_file.exists():
        return False

    try:
        from google.oauth2.credentials import Credentials

        creds = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
            str(token_file), GOOGLE_SCOPES
        )
        return creds.valid or bool(creds.refresh_token)
    except Exception:
        return False
