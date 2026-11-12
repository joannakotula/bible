"""Google Docs and Google Drive access helpers."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

EXPORT_HTML_TEMPLATE = "https://docs.google.com/document/d/{doc_id}/export?format=html"
DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"
DRIVE_EXPORT_URL = DRIVE_FILES_URL + "/{file_id}/export"
GOOGLE_DOC_MIME_TYPE = "application/vnd.google-apps.document"


@dataclass(frozen=True)
class GoogleDoc:
    id: str
    name: str
    html: str


class CredentialTarget(Enum):
    folder = "folder"
    document = "document"


class GoogleApiError(Exception):
    def __init__(
        self,
        status_code: Optional[int],
        reason: Optional[str] = None,
        message: Optional[str] = None,
        *,
        target: Optional[CredentialTarget] = None,
        has_api_key: bool = False,
        has_access_token: bool = False,
    ):
        self.status_code = status_code
        self.reason = reason
        self.message = message
        self.target = target
        self.has_api_key = has_api_key
        self.has_access_token = has_access_token
        details = str(status_code) if status_code is not None else ""
        if reason:
            details = f"{details} {reason}".strip()
        if message:
            details = f"{details}: {message}".strip(": ")
        super().__init__(details or "Google API error")

    def with_context(
        self,
        target: CredentialTarget,
        has_api_key: bool,
        has_access_token: bool,
    ) -> "GoogleApiError":
        self.target = target
        self.has_api_key = has_api_key
        self.has_access_token = has_access_token
        return self

    @property
    def user_message(self) -> str:
        if self.status_code is None:
            return self.message or str(self)
        if self.is_api_key_error():
            return "Google API key was rejected or Google Drive API is not enabled."
        if self.status_code == 401:
            return "Google access token is missing, expired, or invalid."
        if self.status_code == 403:
            if self.target == CredentialTarget.folder:
                if self.has_access_token:
                    return "The access token does not have permission to list this Google Drive folder."
                if self.has_api_key:
                    return (
                        "Google API keys can only list public Drive folders; this folder is private or "
                        "not shared publicly and requires an access token."
                    )
                return _missing_credentials_message(CredentialTarget.folder)
            if self.target == CredentialTarget.document:
                if self.has_access_token:
                    return "The access token does not have permission to read this document."
                return (
                    "The document is private or not shared publicly and requires an access token."
                )
        if self.status_code == 404:
            if self.target == CredentialTarget.folder:
                return (
                    "Google Drive folder was not found or is not shared with the current credentials."
                )
            if self.target == CredentialTarget.document:
                return (
                    "Google document was not found or is not accessible with the current credentials."
                )
        target = self.target.value if self.target else "Google Drive"
        return f"Google {target} request failed ({self})."

    def is_api_key_error(self) -> bool:
        reason = (self.reason or "").lower()
        message = (self.message or "").lower()
        return (
            "keyinvalid" in reason
            or "accessnotconfigured" in reason
            or "service_disabled" in reason
            or "api key" in message
            or "api_key" in message
        )

    @classmethod
    def from_message(
        cls,
        message: str,
        reason: Optional[str] = None,
        target: Optional[CredentialTarget] = None,
    ) -> "GoogleApiError":
        return cls(None, reason, message, target=target)

    @classmethod
    def from_response(cls, response) -> "GoogleApiError":
        reason = None
        message = None
        try:
            data = response.json()
            error = data.get("error", {})
            message = error.get("message")
            errors = error.get("errors") or []
            if errors:
                reason = errors[0].get("reason")
            if not reason:
                reason = error.get("status")
        except Exception:
            text = (response.text or "").strip()
            if text:
                message = text[:300]
        return cls(response.status_code, reason, message)


def _raise_http_error(response) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise GoogleApiError.from_response(response) from exc


def _drive_get(
    url: str,
    params: Optional[dict[str, Any]] = None,
    api_key: Optional[str] = None,
    access_token: Optional[str] = None,
):
    request_params = dict(params or {})
    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    elif api_key:
        request_params["key"] = api_key
    response = requests.get(url, params=request_params, headers=headers, timeout=15)
    _raise_http_error(response)
    return response


def extract_doc_id(url: str) -> Optional[str]:
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    if match:
        return match.group(1)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if 'id' in query:
        return query['id'][0]
    return None


def extract_folder_id(url: str) -> Optional[str]:
    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if "id" in query and parsed.path.rstrip("/").endswith("/folders"):
        return query["id"][0]
    return None


def document_name_from_html(html: str) -> Optional[str]:
    title = BeautifulSoup(html, 'html.parser').title
    if title:
        name = title.get_text(strip=True)
        if name:
            return name
    return None


def list_folder_docs(
    folder_id: str,
    api_key: Optional[str] = None,
    access_token: Optional[str] = None,
) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    page_token: Optional[str] = None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and mimeType='{GOOGLE_DOC_MIME_TYPE}' and trashed=false",
            "fields": "nextPageToken,files(id,name)",
            "pageSize": 1000,
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if page_token:
            params["pageToken"] = page_token
        response = _drive_get(DRIVE_FILES_URL, params, api_key, access_token)
        data = response.json()
        files.extend(data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            return files


def _is_google_login_page(response) -> bool:
    url = (getattr(response, "url", "") or "").lower()
    if "accounts.google.com" in url or "servicelogin" in url:
        return True
    try:
        title = BeautifulSoup(response.text, "html.parser").title
        if title:
            title_text = title.get_text(" ", strip=True).lower()
            return any(text in title_text for text in ("sign in", "log in", "zaloguj"))
    except Exception:
        pass
    return False


def fetch_drive_export(
    file_id: str,
    api_key: Optional[str] = None,
    access_token: Optional[str] = None,
) -> str:
    if access_token:
        response = _drive_get(
            DRIVE_EXPORT_URL.format(file_id=file_id),
            {"mimeType": "text/html"},
            access_token=access_token,
        )
        return response.text

    response = requests.get(EXPORT_HTML_TEMPLATE.format(doc_id=file_id), timeout=15)
    if _is_google_login_page(response):
        raise GoogleApiError.from_message(
            "Google returned a sign-in page instead of the document. The document is private or "
            "not shared publicly and requires an access token.",
            reason="loginRequired",
        )
    if response.status_code == 200 and response.text.strip():
        return response.text

    last_error: Optional[GoogleApiError] = None
    if api_key:
        try:
            response = _drive_get(
                DRIVE_EXPORT_URL.format(file_id=file_id),
                {"mimeType": "text/html"},
                api_key=api_key,
            )
            return response.text
        except GoogleApiError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error

    _raise_http_error(response)
    return response.text


def _missing_credentials_message(target: CredentialTarget) -> str:
    if target == CredentialTarget.folder:
        return "Google Drive folder access requires a Google API key or access token."
    return "The document is not publicly accessible and requires an access token."


class GoogleDriveApi:
    def __init__(self, api_key: Optional[str] = None, access_token: Optional[str] = None):
        self.api_key = api_key
        self.access_token = access_token

    @staticmethod
    def is_folder_url(url: str) -> bool:
        return extract_folder_id(url) is not None

    def fetch_doc(self, url: str) -> GoogleDoc:
        if self.is_folder_url(url):
            raise ValueError("Expected a Google Docs document URL, got a Google Drive folder URL")
        doc_id = extract_doc_id(url)
        if not doc_id:
            raise ValueError("Could not extract a Google Docs document ID from the URL")

        try:
            html = fetch_drive_export(doc_id, self.api_key, self.access_token)
        except GoogleApiError as exc:
            exc.with_context(CredentialTarget.document, bool(self.api_key), bool(self.access_token))
            raise

        name = document_name_from_html(html) or doc_id
        return GoogleDoc(id=doc_id, name=name, html=html)

    def fetch_docs_from_folder(self, url: str) -> list[GoogleDoc]:
        folder_id = extract_folder_id(url)
        if not folder_id:
            raise ValueError("Expected a Google Drive folder URL")

        if not self.api_key and not self.access_token:
            raise GoogleApiError.from_message(
                _missing_credentials_message(CredentialTarget.folder),
                reason="credentialsRequired",
                target=CredentialTarget.folder,
            )

        try:
            items = list_folder_docs(folder_id, self.api_key, self.access_token)
        except GoogleApiError as exc:
            exc.with_context(CredentialTarget.folder, bool(self.api_key), bool(self.access_token))
            raise

        docs: list[GoogleDoc] = []
        for item in items:
            file_id = item["id"]
            name = item.get("name") or file_id
            try:
                html = fetch_drive_export(file_id, self.api_key, self.access_token)
            except GoogleApiError as exc:
                exc.with_context(CredentialTarget.document, bool(self.api_key), bool(self.access_token))
                raise
            docs.append(GoogleDoc(id=file_id, name=name, html=html))
        return docs
