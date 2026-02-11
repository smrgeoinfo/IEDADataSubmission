"""
Orchestration services for the ADA Bridge.

Coordinates the translator, client, and bundle service to implement the
high-level operations exposed by the API views.
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from typing import Any, Dict, Optional

from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone

from ada_bridge.bundle_service import introspect_bundle
from ada_bridge.client import AdaClient
from ada_bridge.models import AdaRecordLink, BundleSession
from ada_bridge.translator_ada import (
    ada_to_jsonld_status,
    compute_payload_checksum,
    jsonld_to_ada,
)
from records.models import Record

logger = logging.getLogger(__name__)


def _get_client() -> AdaClient:
    """Return a configured AdaClient using Django settings."""
    return AdaClient()


def push_record_to_ada(ieda_record_id) -> AdaRecordLink:
    """
    Translate an IEDA record's JSON-LD and push it to ADA.

    1. Fetch the IEDA Record by its primary key.
    2. Translate JSON-LD metadata -> ADA API payload.
    3. Compute payload checksum; skip push if unchanged.
    4. Create (POST) or update (PATCH) in ADA.
    5. Save/update the ``AdaRecordLink``.

    Parameters
    ----------
    ieda_record_id
        Primary key of the ``records.Record``.

    Returns
    -------
    AdaRecordLink
        The created or updated link object.

    Raises
    ------
    records.models.Record.DoesNotExist
        If the record is not found.
    ada_bridge.client.AdaClientError
        If the ADA API returns an error.
    """
    record = Record.objects.select_related("profile").get(pk=ieda_record_id)
    profile_name = record.profile.name if record.profile else ""

    # Translate
    payload = jsonld_to_ada(record.jsonld, profile=profile_name)
    checksum = compute_payload_checksum(payload)

    # Check for existing link
    try:
        link = AdaRecordLink.objects.get(ieda_record=record)
    except AdaRecordLink.DoesNotExist:
        link = None

    # Skip if unchanged
    if link and link.push_checksum == checksum:
        logger.info("Record %s unchanged (checksum match), skipping push.", ieda_record_id)
        return link

    client = _get_client()
    now = timezone.now()

    if link:
        # Update existing ADA record via DOI
        ada_response = client.update_record(link.ada_doi, payload)
        link.last_pushed_at = now
        link.push_checksum = checksum
        ada_to_jsonld_status(ada_response, link)
        link.save()
        logger.info("Updated ADA record %s (DOI %s) for IEDA record %s.", link.ada_record_id, link.ada_doi, ieda_record_id)
    else:
        # Create new ADA record
        ada_response = client.create_record(payload)
        ada_record_id = ada_response.get("id")
        ada_doi = ada_response.get("doi", "")
        link = AdaRecordLink(
            ieda_record=record,
            ada_record_id=ada_record_id,
            ada_doi=ada_doi,
            last_pushed_at=now,
            push_checksum=checksum,
        )
        ada_to_jsonld_status(ada_response, link)
        link.save()
        logger.info("Created ADA record %s (DOI %s) for IEDA record %s.", ada_record_id, ada_doi, ieda_record_id)

    return link


def sync_ada_status(ieda_record_id) -> AdaRecordLink:
    """
    Pull status and DOI from ADA for an IEDA record.

    1. Look up ``AdaRecordLink`` for this record.
    2. GET the ADA record to fetch current status + DOI.
    3. Update the link fields.

    Parameters
    ----------
    ieda_record_id
        Primary key of the ``records.Record``.

    Returns
    -------
    AdaRecordLink
        The updated link object.

    Raises
    ------
    AdaRecordLink.DoesNotExist
        If no link exists for this record.
    """
    link = AdaRecordLink.objects.select_related("ieda_record").get(
        ieda_record_id=ieda_record_id,
    )

    client = _get_client()
    ada_response = client.get_record_status(link.ada_doi)
    ada_to_jsonld_status(ada_response, link)
    link.last_synced_at = timezone.now()
    link.save()

    logger.info(
        "Synced ADA status for IEDA record %s: status=%s, doi=%s",
        ieda_record_id,
        link.ada_status,
        link.ada_doi,
    )
    return link


def upload_bundle_and_introspect(
    file_obj: UploadedFile,
    ieda_record_id=None,
) -> Dict[str, Any]:
    """
    Save an uploaded file to a temp location, introspect it, and optionally
    push the bundle to a linked ADA record.

    Parameters
    ----------
    file_obj : UploadedFile
        The uploaded ZIP file from the request.
    ieda_record_id : optional
        If provided and an ``AdaRecordLink`` exists, also upload the bundle
        to ADA via the client.

    Returns
    -------
    dict
        Introspection results from ``bundle_service.introspect_bundle``,
        plus an optional ``"ada_upload"`` key if the bundle was pushed.
    """
    # Write uploaded file to a temp location
    suffix = ".zip"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        for chunk in file_obj.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        # Introspect
        result = introspect_bundle(tmp_path)

        # Optionally push bundle to ADA
        if ieda_record_id is not None:
            try:
                link = AdaRecordLink.objects.get(ieda_record_id=ieda_record_id)
                client = _get_client()
                with open(tmp_path, "rb") as f:
                    ada_upload_response = client.upload_bundle(
                        link.ada_doi, f
                    )
                result["ada_upload"] = ada_upload_response
            except AdaRecordLink.DoesNotExist:
                result.setdefault("warnings", []).append(
                    "No ADA link exists for this record; bundle was not uploaded to ADA."
                )

        return result
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Session-based bundle services
# ---------------------------------------------------------------------------


def create_bundle_session(
    user,
    file_obj: Optional[UploadedFile] = None,
    url: Optional[str] = None,
) -> BundleSession:
    """
    Create a BundleSession from an uploaded file or URL.

    Saves the uploaded file to a temp location and creates a session record.
    If a URL is provided, downloads it first.

    Returns
    -------
    BundleSession
        The newly created session.
    """
    if file_obj:
        suffix = ".zip"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, dir=tempfile.gettempdir()) as tmp:
            for chunk in file_obj.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
    elif url:
        import requests as req

        resp = req.get(url, stream=True, timeout=120)
        resp.raise_for_status()
        suffix = ".zip"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, dir=tempfile.gettempdir()) as tmp:
            for chunk in resp.iter_content(chunk_size=8192):
                tmp.write(chunk)
            tmp_path = tmp.name
    else:
        raise ValueError("Either 'file' or 'url' must be provided.")

    session = BundleSession.objects.create(
        user=user if user.is_authenticated else None,
        bundle_path=tmp_path,
        status=BundleSession.Status.CREATED,
    )
    logger.info("Created bundle session %s from %s", session.session_id, "upload" if file_obj else url)
    return session


def introspect_bundle_session(session: BundleSession) -> BundleSession:
    """
    Run introspection on a bundle session's file.

    1. Check for product.yaml in the bundle
    2. Run file inspectors
    3. If product_yaml is set on the session, use it for full processing
    4. Store results in the session

    Returns
    -------
    BundleSession
        The updated session with introspection_result populated.
    """
    if not os.path.isfile(session.bundle_path):
        raise FileNotFoundError(f"Bundle file not found at {session.bundle_path}")

    session.status = BundleSession.Status.INTROSPECTING
    session.save(update_fields=["status", "updated_at"])

    # Run introspection
    result = introspect_bundle(session.bundle_path)

    # Check for product.yaml in the manifest
    product_yaml_found = False
    for filepath in result.get("manifest", []):
        basename = os.path.basename(filepath).lower()
        if basename in ("product.yaml", "product.yml"):
            product_yaml_found = True
            # Try to parse it
            try:
                import zipfile
                import yaml

                with zipfile.ZipFile(session.bundle_path, "r") as zf:
                    with zf.open(filepath) as f:
                        product_data = yaml.safe_load(f)
                        if isinstance(product_data, dict):
                            session.product_yaml = product_data
            except Exception:
                logger.exception("Failed to parse product.yaml from bundle")
            break

    session.introspection_result = result
    session.status = BundleSession.Status.READY
    session.save(update_fields=["product_yaml", "introspection_result", "status", "updated_at"])

    logger.info(
        "Introspected bundle session %s: %d files, product.yaml=%s",
        session.session_id,
        len(result.get("manifest", [])),
        "found" if product_yaml_found else "missing",
    )
    return session


def submit_bundle_session(
    session: BundleSession,
    catalog_record_id=None,
) -> Dict[str, Any]:
    """
    Submit a bundle session: push the associated catalog record to ADA.

    Parameters
    ----------
    session : BundleSession
        The bundle session to submit.
    catalog_record_id : optional
        Existing catalog record ID. If provided, push that record to ADA.

    Returns
    -------
    dict
        Result including catalog_record_id and ADA push status.
    """
    result: Dict[str, Any] = {
        "session_id": str(session.session_id),
        "status": "submitted",
    }

    if catalog_record_id:
        try:
            link = push_record_to_ada(catalog_record_id)
            result["ada_record_id"] = link.ada_record_id
            result["ada_doi"] = link.ada_doi
            result["ada_status"] = link.ada_status
        except Record.DoesNotExist:
            result["warning"] = "Catalog record not found; ADA push skipped."
        except Exception as exc:
            # Generate a placeholder DOI if ADA push fails
            placeholder_doi = f"doi:10.xxxxx/placeholder-{uuid.uuid4()}"
            result["warning"] = f"ADA push failed ({exc}); placeholder DOI assigned."
            result["placeholder_doi"] = placeholder_doi
            result["ada_status"] = "pending_doi"

    session.status = BundleSession.Status.SUBMITTED
    session.save(update_fields=["status", "updated_at"])

    return result
