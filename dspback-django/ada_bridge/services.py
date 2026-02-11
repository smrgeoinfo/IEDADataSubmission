"""
Orchestration services for the ADA Bridge.

Coordinates the translator, client, and bundle service to implement the
high-level operations exposed by the API views.
"""

from __future__ import annotations

import logging
import tempfile
from typing import Any, Dict

from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone

from ada_bridge.bundle_service import introspect_bundle
from ada_bridge.client import AdaClient
from ada_bridge.models import AdaRecordLink
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
        import os

        try:
            os.unlink(tmp_path)
        except OSError:
            pass
