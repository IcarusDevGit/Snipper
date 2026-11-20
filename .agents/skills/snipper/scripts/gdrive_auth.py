"""Google Drive and Google Docs authentication helper supporting Service Account and OAuth 2.0 flows."""

import os
from pathlib import Path
import sys
from typing import Any, Optional

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]


def get_credentials(
    credentials_path: Optional[str | Path] = None,
    service_account_path: Optional[str | Path] = None,
    token_cache_path: Optional[str | Path] = None,
) -> Any:
    """Resolves and returns authorized Google credentials for Drive and Docs APIs."""
    # 1. Try Service Account first (headless/non-interactive)
    sa_file = (
        service_account_path
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or ("service_account.json" if Path("service_account.json").exists() else None)
    )

    if sa_file and Path(sa_file).exists():
        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_file(
            str(sa_file), scopes=SCOPES
        )

    # 2. Try OAuth 2.0 Desktop Client Flow
    root_dir = Path(__file__).resolve().parents[4]
    token_file = Path(token_cache_path) if token_cache_path else (Path("token.json") if Path("token.json").exists() else root_dir / "token.json")
    creds = None
    if token_file.exists():
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                token_file.write_text(creds.to_json(), encoding="utf-8")
                return creds
            except Exception as e:
                print(f"[*] Stored token refresh failed ({e}); re-authenticating via OAuth flow...")
                creds = None

    root_dir = Path(__file__).resolve().parents[4]
    oauth_file = credentials_path
    if not oauth_file:
        candidates = [
            Path("credentials.json"),
            root_dir / "credentials.json",
        ] + list(Path(".").glob("client_secret_*.json")) + list(root_dir.glob("client_secret_*.json"))
        for cand in candidates:
            if cand.exists():
                oauth_file = cand
                break

    if oauth_file and Path(oauth_file).exists():
        from google_auth_oauthlib.flow import InstalledAppFlow
        import socket
        import webbrowser

        class WindowsStartfileBrowser:
            def open(self, url, new=0, autoraise=True):
                try:
                    if hasattr(os, "startfile"):
                        os.startfile(url)
                        return True
                except Exception:
                    pass
                return False

        try:
            webbrowser.register("startfile", None, WindowsStartfileBrowser(), preferred=True)
        except Exception:
            pass

        flow = InstalledAppFlow.from_client_secrets_file(str(oauth_file), SCOPES)

        # Allocate free local port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("localhost", 0))
        port = sock.getsockname()[1]
        sock.close()

        prompt_msg = "\n[!] Please authorize Google Drive & Docs by opening this URL:\n{url}\n"
        creds = flow.run_local_server(
            port=port,
            open_browser=True,
            browser="startfile",
            authorization_prompt_message=prompt_msg,
        )
        token_file.write_text(creds.to_json(), encoding="utf-8")
        return creds

    raise FileNotFoundError(
        "[!] No Google Drive credentials found.\n"
        "[!] Please provide 'service_account.json' or 'credentials.json' for OAuth."
    )


def get_drive_service(
    credentials_path: Optional[str | Path] = None,
    service_account_path: Optional[str | Path] = None,
    token_cache_path: Optional[str | Path] = None,
) -> Any:
    """Authenticates and returns an authorized Google Drive API service resource (v3)."""
    try:
        from googleapiclient.discovery import build
    except ImportError as e:
        raise RuntimeError(
            "[!] Google Drive extension requires optional dependencies.\n"
            "[!] Install them with: pip install -r requirements-gdrive.txt"
        ) from e

    creds = get_credentials(
        credentials_path=credentials_path,
        service_account_path=service_account_path,
        token_cache_path=token_cache_path,
    )
    return build("drive", "v3", credentials=creds)


def get_docs_service(
    credentials_path: Optional[str | Path] = None,
    service_account_path: Optional[str | Path] = None,
    token_cache_path: Optional[str | Path] = None,
) -> Any:
    """Authenticates and returns an authorized Google Docs API service resource (v1)."""
    try:
        from googleapiclient.discovery import build
    except ImportError as e:
        raise RuntimeError(
            "[!] Google Drive extension requires optional dependencies.\n"
            "[!] Install them with: pip install -r requirements-gdrive.txt"
        ) from e

    creds = get_credentials(
        credentials_path=credentials_path,
        service_account_path=service_account_path,
        token_cache_path=token_cache_path,
    )
    return build("docs", "v1", credentials=creds)
