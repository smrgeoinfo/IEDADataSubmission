"""
HTTP client for the ADA (Astromat Data Archive) REST API.

ADA uses ``djangorestframework-api-key`` for authentication.  The API key
is passed in the ``Authorization: Api-Key <key>`` header.

Usage::

    from ada_bridge.client import AdaClient
    client = AdaClient(base_url="http://localhost:8000", api_key="abc123")
    record = client.create_record(payload)
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class AdaClientError(Exception):
    """Raised when the ADA API returns a non-success response."""

    def __init__(self, status_code: int, detail: Any = None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"ADA API error {status_code}: {detail}")


class AdaClient:
    """Thin wrapper around the ADA REST API."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = 30,
    ):
        self.base_url = (base_url or getattr(settings, "ADA_API_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or getattr(settings, "ADA_API_KEY", "")
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _handle_response(self, response: requests.Response) -> dict:
        if response.status_code < 200 or response.status_code >= 300:
            try:
                detail = response.json()
            except (ValueError, requests.JSONDecodeError):
                detail = response.text
            logger.error(
                "ADA API %s %s -> %s: %s",
                response.request.method,
                response.request.url,
                response.status_code,
                detail,
            )
            raise AdaClientError(response.status_code, detail)

        if response.status_code == 204:
            return {}
        return response.json()

    # ------------------------------------------------------------------
    # Record CRUD
    # ------------------------------------------------------------------

    def create_record(self, payload: dict) -> dict:
        """POST /api/record/ — create a new record in ADA."""
        response = self.session.post(
            self._url("/api/record/"),
            json=payload,
            timeout=self.timeout,
        )
        return self._handle_response(response)

    def update_record(self, record_doi: str, payload: dict) -> dict:
        """PATCH /api/record/{doi} — update an existing ADA record."""
        response = self.session.patch(
            self._url(f"/api/record/{record_doi}"),
            json=payload,
            timeout=self.timeout,
        )
        return self._handle_response(response)

    def get_record(self, record_doi: str) -> dict:
        """GET /api/record/{doi} — fetch a single ADA record."""
        response = self.session.get(
            self._url(f"/api/record/{record_doi}"),
            timeout=self.timeout,
        )
        return self._handle_response(response)

    # ------------------------------------------------------------------
    # Bundle / file upload
    # ------------------------------------------------------------------

    def upload_bundle(self, record_doi: str, file_obj) -> dict:
        """
        POST /api/download/{doi}/ — upload a bundle to an ADA record.

        ``file_obj`` should be a file-like object opened in binary mode.
        """
        # Remove Content-Type so requests sets multipart boundary automatically
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Accept": "application/json",
        }
        response = requests.post(
            self._url(f"/api/download/{record_doi}/"),
            files={"file": file_obj},
            headers=headers,
            timeout=self.timeout,
        )
        return self._handle_response(response)

    # ------------------------------------------------------------------
    # Status / DOI
    # ------------------------------------------------------------------

    def get_record_status(self, record_doi: str) -> dict:
        """
        GET /api/record/{doi} — fetch status and DOI info.

        Returns the full record; callers typically only need
        ``process_status`` and ``doi``.
        """
        return self.get_record(record_doi)
