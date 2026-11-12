import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

import parse_gdoc
from lib import google_docs
from lib.google_docs import GoogleDoc, GoogleDriveApi, document_name_from_html
from parse_gdoc import slugify


def make_doc_html(title: str) -> str:
    return (
        f"<html><head><title>{title}</title></head><body>"
        "<h1>Streszczenie</h1><p>J 2, 1: Pierwszy werset.</p>"
        "<h1>Wzmianki</h1><p>J 2, 1: Pierwszy werset.</p>"
        "</body></html>"
    )


class FakeResponse:
    def __init__(self, data=None, text="", status_code=200, url=""):
        self.data = data or {}
        self.text = text
        self.status_code = status_code
        self.url = url

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Client Error")


class TestSlugify(unittest.TestCase):
    def test_transliterates_polish_characters(self):
        self.assertEqual(slugify("Zażółć Gęślą Jaźń!"), "zazolc-gesla-jazn")

    def test_collapses_separators(self):
        self.assertEqual(slugify("  Foo -- Bar  "), "foo-bar")

    def test_uses_fallback_for_empty_name(self):
        self.assertEqual(slugify("!!!"), "document")


class TestDocumentNameFromHtml(unittest.TestCase):
    def test_returns_title(self):
        self.assertEqual(document_name_from_html(make_doc_html("My Doc")), "My Doc")

    def test_returns_none_without_title(self):
        self.assertIsNone(document_name_from_html("<html><body></body></html>"))


class TestExtractIds(unittest.TestCase):
    def test_extracts_document_id(self):
        url = "https://docs.google.com/document/d/abc123/edit"
        self.assertEqual(google_docs.extract_doc_id(url), "abc123")

    def test_extracts_folder_id(self):
        url = "https://drive.google.com/drive/folders/folder123?usp=sharing"
        self.assertEqual(google_docs.extract_folder_id(url), "folder123")

    def test_document_url_has_no_folder_id(self):
        url = "https://docs.google.com/document/d/abc123/edit"
        self.assertIsNone(google_docs.extract_folder_id(url))

    def test_is_folder_url(self):
        self.assertTrue(GoogleDriveApi.is_folder_url("https://drive.google.com/drive/folders/folder123"))
        self.assertFalse(GoogleDriveApi.is_folder_url("https://docs.google.com/document/d/abc123/edit"))


class TestListFolderDocs(unittest.TestCase):
    def test_follows_pagination_and_requests_only_google_docs(self):
        responses = [
            FakeResponse({
                "files": [{"id": "1", "name": "First Doc"}],
                "nextPageToken": "next-page",
            }),
            FakeResponse({
                "files": [{"id": "2", "name": "Second Doc"}],
            }),
        ]

        with patch.object(google_docs, "_drive_get", side_effect=responses) as drive_get:
            docs = google_docs.list_folder_docs("folder123", api_key="api-key")

        self.assertEqual([doc["id"] for doc in docs], ["1", "2"])
        self.assertEqual(drive_get.call_count, 2)
        first_params = drive_get.call_args_list[0].args[1]
        self.assertIn("application/vnd.google-apps.document", first_params["q"])
        self.assertIn("'folder123' in parents", first_params["q"])


class TestGoogleDriveApi(unittest.TestCase):
    def test_fetch_doc_returns_named_document(self):
        html = make_doc_html("Remote Doc")
        api = GoogleDriveApi()

        with patch.object(google_docs, "fetch_drive_export", return_value=html):
            doc = api.fetch_doc("https://docs.google.com/document/d/abc123/edit")

        self.assertEqual(doc, GoogleDoc(id="abc123", name="Remote Doc", html=html))

    def test_fetch_doc_falls_back_to_document_id(self):
        html = "<html><body>No title</body></html>"
        api = GoogleDriveApi()

        with patch.object(google_docs, "fetch_drive_export", return_value=html):
            doc = api.fetch_doc("https://docs.google.com/document/d/abc123/edit")

        self.assertEqual(doc.name, "abc123")

    def test_fetch_docs_from_folder_returns_documents(self):
        items = [
            {"id": "1", "name": "First Doc"},
            {"id": "2", "name": "Second Doc"},
        ]
        html = make_doc_html("Unused Title")
        api = GoogleDriveApi(api_key="api-key")

        with (
            patch.object(google_docs, "list_folder_docs", return_value=items),
            patch.object(google_docs, "fetch_drive_export", return_value=html),
        ):
            docs = api.fetch_docs_from_folder("https://drive.google.com/drive/folders/folder123")

        self.assertEqual(
            [(doc.id, doc.name) for doc in docs],
            [("1", "First Doc"), ("2", "Second Doc")],
        )

    def test_fetch_docs_from_folder_requires_credentials(self):
        api = GoogleDriveApi()

        with self.assertRaises(google_docs.GoogleApiError) as raised:
            api.fetch_docs_from_folder("https://drive.google.com/drive/folders/folder123")

        self.assertIn("API key", raised.exception.user_message)
        self.assertIn("access token", raised.exception.user_message)
        self.assertNotIn("GOOGLE_API_KEY", raised.exception.user_message)
        self.assertNotIn("GOOGLE_ACCESS_TOKEN", raised.exception.user_message)

    def test_fetch_docs_from_folder_private_with_api_key_mentions_access_token(self):
        error = google_docs.GoogleApiError(403, "forbidden", "Insufficient permissions")
        api = GoogleDriveApi(api_key="api-key")

        with patch.object(google_docs, "list_folder_docs", side_effect=error):
            with self.assertRaises(google_docs.GoogleApiError) as raised:
                api.fetch_docs_from_folder("https://drive.google.com/drive/folders/folder123")

        self.assertIn("access token", raised.exception.user_message)
        self.assertIn("private", raised.exception.user_message)
        self.assertNotIn("GOOGLE_ACCESS_TOKEN", raised.exception.user_message)

    def test_fetch_doc_private_without_credentials_mentions_access_token(self):
        error = google_docs.GoogleApiError(403, "forbidden", "Insufficient permissions")
        api = GoogleDriveApi()

        with patch.object(google_docs, "fetch_drive_export", side_effect=error):
            with self.assertRaises(google_docs.GoogleApiError) as raised:
                api.fetch_doc("https://docs.google.com/document/d/abc123/edit")

        self.assertIn("access token", raised.exception.user_message)
        self.assertNotIn("GOOGLE_ACCESS_TOKEN", raised.exception.user_message)


class TestMainOutput(unittest.TestCase):
    def test_single_url_document_writes_to_directory_using_title_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            out_dir.mkdir()
            argv = [
                "parse_gdoc.py",
                "https://docs.google.com/document/d/abc123/edit",
                "--out",
                str(out_dir),
            ]
            doc = GoogleDoc(id="abc123", name="Remote Doc", html=make_doc_html("Remote Doc"))

            with (
                patch.object(parse_gdoc.GoogleDriveApi, "fetch_doc", return_value=doc),
                patch.object(sys, "argv", argv),
            ):
                parse_gdoc.main()

            self.assertTrue((out_dir / "remote-doc.txt").is_file())

    def test_drive_folder_writes_one_file_per_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            out_dir.mkdir()
            argv = [
                "parse_gdoc.py",
                "https://drive.google.com/drive/folders/folder123",
                "--out",
                str(out_dir),
                "--api-key",
                "api-key",
            ]
            docs = [
                GoogleDoc(id="1", name="First Doc", html=make_doc_html("First Doc")),
                GoogleDoc(id="2", name="Second Doc", html=make_doc_html("Second Doc")),
            ]

            with (
                patch.object(parse_gdoc.GoogleDriveApi, "fetch_docs_from_folder", return_value=docs),
                patch.object(sys, "argv", argv),
            ):
                parse_gdoc.main()

            self.assertEqual(
                sorted(path.name for path in out_dir.iterdir()),
                ["first-doc.txt", "second-doc.txt"],
            )

    def test_drive_folder_rejects_file_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_file = Path(tmp) / "out.txt"
            out_file.write_text("", encoding="UTF-8")
            argv = [
                "parse_gdoc.py",
                "https://drive.google.com/drive/folders/folder123",
                "--out",
                str(out_file),
            ]

            with (
                patch.object(sys, "argv", argv),
                patch.object(sys, "stderr", new=io.StringIO()),
            ):
                with self.assertRaises(SystemExit) as raised:
                    parse_gdoc.main()

            self.assertEqual(raised.exception.code, 2)


class TestGoogleErrors(unittest.TestCase):
    def test_extracts_google_error_reason(self):
        response = FakeResponse(
            {"error": {"message": "API key not valid", "errors": [{"reason": "keyInvalid"}]}},
            status_code=403,
        )

        error = google_docs.GoogleApiError.from_response(response)
        error.with_context(google_docs.CredentialTarget.folder, True, False)

        self.assertEqual(error.status_code, 403)
        self.assertEqual(error.reason, "keyInvalid")
        self.assertTrue(error.is_api_key_error())
        self.assertIn("API key", error.user_message)
        self.assertNotIn("GOOGLE_API_KEY", error.user_message)

    def test_drive_get_converts_http_error_to_google_api_error(self):
        response = FakeResponse(
            {"error": {"message": "API key not valid", "errors": [{"reason": "keyInvalid"}]}},
            status_code=403,
        )

        with patch.object(google_docs.requests, "get", return_value=response):
            with self.assertRaises(google_docs.GoogleApiError) as raised:
                google_docs._drive_get("https://example.test/files", api_key="bad-key")

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.reason, "keyInvalid")

    def test_key_error_with_400_mentions_api_key(self):
        error = google_docs.GoogleApiError(400, "keyInvalid", "API key not valid")
        error.with_context(google_docs.CredentialTarget.folder, True, False)

        self.assertIn("API key", error.user_message)
        self.assertNotIn("GOOGLE_API_KEY", error.user_message)

    def test_private_folder_with_api_key_mentions_access_token(self):
        error = google_docs.GoogleApiError(403, "forbidden", "Insufficient permissions")
        error.with_context(google_docs.CredentialTarget.folder, True, False)

        self.assertIn("access token", error.user_message)
        self.assertIn("private", error.user_message)
        self.assertNotIn("GOOGLE_ACCESS_TOKEN", error.user_message)

    def test_expired_token_mentions_access_token(self):
        error = google_docs.GoogleApiError(401, "authError", "Invalid Credentials")
        error.with_context(google_docs.CredentialTarget.folder, False, True)

        self.assertIn("expired", error.user_message.lower())
        self.assertIn("access token", error.user_message)
        self.assertNotIn("GOOGLE_ACCESS_TOKEN", error.user_message)

    def test_private_document_without_credentials_mentions_access_token(self):
        error = google_docs.GoogleApiError(403, "forbidden", "Insufficient permissions")
        error.with_context(google_docs.CredentialTarget.document, False, False)

        self.assertIn("access token", error.user_message)
        self.assertNotIn("GOOGLE_ACCESS_TOKEN", error.user_message)

    def test_detects_google_login_page(self):
        response = FakeResponse(
            text="<html><head><title>Sign in</title></head></html>",
            url="https://accounts.google.com/ServiceLogin",
        )

        self.assertTrue(google_docs._is_google_login_page(response))

    def test_login_page_reports_private_document(self):
        response = FakeResponse(
            text="<html><head><title>Sign in</title></head></html>",
            url="https://accounts.google.com/ServiceLogin",
        )

        with patch.object(google_docs.requests, "get", return_value=response):
            with self.assertRaises(google_docs.GoogleApiError) as raised:
                google_docs.fetch_drive_export("doc123")

        self.assertIsNone(raised.exception.status_code)
        self.assertEqual(raised.exception.reason, "loginRequired")
        self.assertIn("access token", raised.exception.user_message)
        self.assertNotIn("GOOGLE_ACCESS_TOKEN", raised.exception.user_message)

    def test_login_page_error_message_is_actionable(self):
        error = google_docs.GoogleApiError.from_message(
            "Google returned a sign-in page instead of the document.",
            reason="loginRequired",
        )

        self.assertIn("sign-in", error.user_message)


class TestMainGoogleErrors(unittest.TestCase):
    def test_folder_without_credentials_reports_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            out_dir.mkdir()
            argv = [
                "parse_gdoc.py",
                "https://drive.google.com/drive/folders/folder123",
                "--out",
                str(out_dir),
            ]
            stderr = io.StringIO()

            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(sys, "argv", argv),
                patch.object(sys, "stderr", new=stderr),
            ):
                with self.assertRaises(SystemExit) as raised:
                    parse_gdoc.main()

            self.assertEqual(raised.exception.code, 2)
            self.assertIn("GOOGLE_API_KEY", stderr.getvalue())
            self.assertIn("GOOGLE_ACCESS_TOKEN", stderr.getvalue())

    def test_private_folder_with_api_key_reports_access_token_requirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            out_dir.mkdir()
            argv = [
                "parse_gdoc.py",
                "https://drive.google.com/drive/folders/folder123",
                "--out",
                str(out_dir),
                "--api-key",
                "api-key",
            ]
            stderr = io.StringIO()
            error = google_docs.GoogleApiError(403, "forbidden", "Insufficient permissions")

            with (
                patch.object(google_docs, "list_folder_docs", side_effect=error),
                patch.object(sys, "argv", argv),
                patch.object(sys, "stderr", new=stderr),
            ):
                with self.assertRaises(SystemExit) as raised:
                    parse_gdoc.main()

            self.assertEqual(raised.exception.code, 2)
            self.assertIn("access token", stderr.getvalue())

    def test_private_document_without_credentials_reports_access_token_requirement(self):
        argv = [
            "parse_gdoc.py",
            "https://docs.google.com/document/d/abc123/edit",
        ]
        stderr = io.StringIO()
        error = google_docs.GoogleApiError(403, "forbidden", "Insufficient permissions")

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(google_docs, "fetch_drive_export", side_effect=error),
            patch.object(sys, "argv", argv),
            patch.object(sys, "stderr", new=stderr),
        ):
            with self.assertRaises(SystemExit) as raised:
                parse_gdoc.main()

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("access token", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
