"""
Translate JSON-LD (schema:-prefixed) metadata to ADA API format.

The ADA API (astromat_api) expects camelCase fields matching
``ListRecordSerializer`` / ``RecordSerializer`` in
``ADA/api/astromat_api/serializers/record_serializers.py``.

The source metadata is the JSON-LD stored in ``records.Record.jsonld``,
produced by the IEDADataSubmission metadata forms.

Public API:
    jsonld_to_ada(record_metadata, profile) -> dict
    ada_to_jsonld_status(ada_response, link)  -> None (mutates link)
    compute_payload_checksum(payload)          -> str
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers (reuse patterns from dspback translator)
# ---------------------------------------------------------------------------

def _strip_prefix(key: str) -> str:
    """Remove a namespace prefix (e.g. ``'schema:name'`` -> ``'name'``)."""
    if ":" in key and not key.startswith("@"):
        return key.split(":", 1)[1]
    return key


def _get(obj: dict, prefixed_key: str, default=None):
    """Get a value trying both the prefixed and bare key."""
    if prefixed_key in obj:
        return obj[prefixed_key]
    bare = _strip_prefix(prefixed_key)
    if bare in obj:
        return obj[bare]
    return default


# ---------------------------------------------------------------------------
# Section translators — JSON-LD -> ADA API fields
# ---------------------------------------------------------------------------

def _translate_creators(jsonld: dict) -> List[Dict[str, Any]]:
    """
    ``schema:creator`` -> ADA ``creators[]`` (via ``RecordCreatorSerializer``).

    ADA expects each creator as::

        {
            "name_entity": {
                "full_name": "...",
                "given_name": "...",
                "family_name": "...",
                "name_type": "Personal" | "Organizational",
            }
        }
    """
    raw = _get(jsonld, "schema:creator")
    if not raw:
        return []

    creators: list = []
    items = raw if isinstance(raw, list) else [raw]

    for item in items:
        inner_list = item.get("@list", [item]) if isinstance(item, dict) else [item]
        for person in inner_list:
            if not isinstance(person, dict):
                continue

            full_name = _get(person, "schema:name", "")

            raw_type = _get(person, "@type", "schema:Person")
            if isinstance(raw_type, list):
                raw_type = raw_type[0] if raw_type else "schema:Person"
            type_str = _strip_prefix(str(raw_type))

            name_type = "Organizational" if type_str == "Organization" else "Personal"

            given_name = _get(person, "schema:givenName", "")
            family_name = _get(person, "schema:familyName", "")

            # Attempt to split full_name if given/family not provided
            if full_name and not given_name and not family_name and name_type == "Personal":
                parts = full_name.rsplit(" ", 1)
                if len(parts) == 2:
                    given_name, family_name = parts
                else:
                    family_name = full_name

            creator_entry: Dict[str, Any] = {
                "nameEntity": {
                    "fullName": full_name,
                    "givenName": given_name,
                    "familyName": family_name,
                    "nameType": name_type,
                },
            }

            # ORCID identifier
            ident = _get(person, "schema:identifier")
            if isinstance(ident, str) and ident:
                creator_entry["nameEntity"]["orcid"] = ident
            elif isinstance(ident, dict):
                val = _get(ident, "schema:value") or _get(ident, "schema:url")
                if val:
                    creator_entry["nameEntity"]["orcid"] = val

            creators.append(creator_entry)

    return creators


def _translate_contributors(jsonld: dict) -> List[Dict[str, Any]]:
    """
    ``schema:contributor`` -> ADA ``contributors[]`` (``RecordContributorSerializer``).

    Each entry::

        {
            "name_entity": { ... },
            "contributor_type": "..."
        }
    """
    raw = _get(jsonld, "schema:contributor")
    if not raw:
        return []

    contributors: list = []
    for item in (raw if isinstance(raw, list) else [raw]):
        if not isinstance(item, dict):
            continue

        raw_type = _get(item, "@type", "")
        type_str = _strip_prefix(str(raw_type)) if raw_type else ""

        contributor_type = ""
        person_data: dict = item

        if type_str == "Role":
            contributor_type = _get(item, "roleName") or _get(item, "schema:roleName") or ""
            agent = _get(item, "contributor") or _get(item, "schema:contributor") or {}
            if isinstance(agent, dict):
                person_data = agent
            else:
                continue

        full_name = _get(person_data, "schema:name", "")
        given_name = _get(person_data, "schema:givenName", "")
        family_name = _get(person_data, "schema:familyName", "")

        if full_name and not given_name and not family_name:
            parts = full_name.rsplit(" ", 1)
            if len(parts) == 2:
                given_name, family_name = parts
            else:
                family_name = full_name

        entry: Dict[str, Any] = {
            "nameEntity": {
                "fullName": full_name,
                "givenName": given_name,
                "familyName": family_name,
                "nameType": "Personal",
            },
            "contributorType": contributor_type,
        }

        ident = _get(person_data, "schema:identifier")
        if isinstance(ident, str) and ident:
            entry["nameEntity"]["orcid"] = ident

        contributors.append(entry)

    return contributors


def _translate_funding(jsonld: dict) -> List[Dict[str, Any]]:
    """
    ``schema:funding`` -> ADA ``funding[]`` (``RecordFundingSerializer``).

    Each entry::

        {
            "funder": {"name": "..."},
            "award_number": "...",
            "award_title": "...",
        }
    """
    raw = _get(jsonld, "schema:funding")
    if not raw:
        return []

    result = []
    for grant in (raw if isinstance(raw, list) else [raw]):
        if not isinstance(grant, dict):
            continue

        funder_name = ""
        funder = _get(grant, "funder") or _get(grant, "schema:funder")
        if isinstance(funder, dict):
            funder_name = _get(funder, "schema:name", "")
        elif isinstance(funder, str):
            funder_name = funder

        entry: Dict[str, Any] = {
            "funder": {"name": funder_name},
            "awardNumber": _get(grant, "identifier") or _get(grant, "schema:identifier") or "",
            "awardTitle": _get(grant, "name") or _get(grant, "schema:name") or "",
        }
        result.append(entry)
    return result


def _translate_licenses(jsonld: dict) -> List[Dict[str, Any]]:
    """
    ``schema:license`` -> ADA ``licenses[]`` (``LicenseSerializer``).
    """
    raw = _get(jsonld, "schema:license")
    if not raw:
        return []

    result = []
    for item in (raw if isinstance(raw, list) else [raw]):
        if isinstance(item, str):
            result.append({"name": item})
        elif isinstance(item, dict):
            entry: Dict[str, Any] = {}
            name = _get(item, "schema:name")
            if name:
                entry["name"] = name
            url = _get(item, "schema:url")
            if url:
                entry["url"] = url
            description = _get(item, "schema:description")
            if description:
                entry["description"] = description
            result.append(entry)
    return result


def _translate_subjects(jsonld: dict, profile: str) -> List[Dict[str, Any]]:
    """
    Profile-specific fields -> ADA ``subjects[]`` (``RecordSubjectSerializer``).

    Technique, instrument, and other profile-specific metadata is stored
    as subject entries keyed by a ``subject_schema_name``.
    """
    # For now, pass through any subjects already present in the JSON-LD
    raw = _get(jsonld, "schema:about") or _get(jsonld, "subjects")
    if not raw:
        return []

    result = []
    for item in (raw if isinstance(raw, list) else [raw]):
        if not isinstance(item, dict):
            continue
        result.append(item)
    return result


def _translate_files(jsonld: dict) -> List[Dict[str, Any]]:
    """
    ``schema:distribution`` -> ADA ``files[]`` (``RecordFileSerializer``).
    """
    raw = _get(jsonld, "schema:distribution")
    if not raw:
        return []

    result = []
    for d in (raw if isinstance(raw, list) else [raw]):
        if not isinstance(d, dict):
            continue
        name = _get(d, "schema:name") or _get(d, "schema:description") or ""
        entry: Dict[str, Any] = {"name": name}
        encoding = _get(d, "schema:encodingFormat")
        if encoding:
            entry["extension"] = encoding
        result.append(entry)
    return result


# ---------------------------------------------------------------------------
# Main translator
# ---------------------------------------------------------------------------

def jsonld_to_ada(record_metadata: dict, profile: str = "") -> dict:
    """
    Translate a JSON-LD metadata document into the payload expected by the
    ADA ``/api/records/`` endpoint (``ListRecordSerializer``).

    Parameters
    ----------
    record_metadata : dict
        The JSON-LD document from ``Record.jsonld``.
    profile : str
        The profile name (e.g. ``"adaProduct"``, ``"adaEMPA"``).

    Returns
    -------
    dict
        Payload suitable for POST/PATCH to ADA's record API.
    """
    payload: Dict[str, Any] = {}

    # ---- Scalar fields ----
    payload["title"] = _get(record_metadata, "schema:name", "")
    payload["description"] = _get(record_metadata, "schema:description", "")

    submission_type = record_metadata.get("submissionType")
    if submission_type:
        payload["submissionType"] = submission_type

    additional_type = _get(record_metadata, "schema:additionalType")
    if additional_type:
        payload["specificType"] = (
            additional_type if isinstance(additional_type, str)
            else additional_type[0] if additional_type else ""
        )

    date_published = _get(record_metadata, "schema:datePublished")
    if date_published:
        payload["publicationDate"] = date_published

    # ---- Nested / array fields ----
    creators = _translate_creators(record_metadata)
    if creators:
        payload["creators"] = creators

    contributors = _translate_contributors(record_metadata)
    if contributors:
        payload["contributors"] = contributors

    funding = _translate_funding(record_metadata)
    if funding:
        payload["funding"] = funding

    licenses = _translate_licenses(record_metadata)
    if licenses:
        payload["licenses"] = licenses

    subjects = _translate_subjects(record_metadata, profile)
    if subjects:
        payload["subjects"] = subjects

    files = _translate_files(record_metadata)
    if files:
        payload["files"] = files

    return payload


# ---------------------------------------------------------------------------
# Status write-back
# ---------------------------------------------------------------------------

def ada_to_jsonld_status(ada_response: dict, link) -> None:
    """
    Update an ``AdaRecordLink`` with status and DOI from an ADA API response.

    Parameters
    ----------
    ada_response : dict
        The JSON response from ``GET /api/records/{id}/``.
    link : AdaRecordLink
        The link object to update (caller is responsible for saving).
    """
    # ADA renders camelCase via CamelCaseJSONRenderer
    link.ada_status = ada_response.get("processStatus", "") or ada_response.get("process_status", "")
    doi = ada_response.get("doi", "")
    if doi:
        link.ada_doi = doi


# ---------------------------------------------------------------------------
# Checksum
# ---------------------------------------------------------------------------

def compute_payload_checksum(payload: dict) -> str:
    """
    Compute a deterministic SHA-256 hex digest for a payload dict.

    Used to detect whether the translated payload has changed since the
    last push, so unchanged records can be skipped.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Reverse translator — ADA API -> JSON-LD
# ---------------------------------------------------------------------------

def _reverse_creators(ada_creators: list) -> List[Dict[str, Any]]:
    """ADA ``creators[]`` -> ``schema:creator`` JSON-LD."""
    result = []
    for c in ada_creators:
        ne = c.get("nameEntity") or c.get("name_entity") or {}
        person: Dict[str, Any] = {"@type": "schema:Person"}

        full_name = ne.get("fullName") or ne.get("full_name", "")
        if full_name:
            person["schema:name"] = full_name

        given = ne.get("givenName") or ne.get("given_name", "")
        if given:
            person["schema:givenName"] = given

        family = ne.get("familyName") or ne.get("family_name", "")
        if family:
            person["schema:familyName"] = family

        name_type = ne.get("nameType") or ne.get("name_type", "")
        if name_type == "Organizational":
            person["@type"] = "schema:Organization"

        orcid = ne.get("orcid", "")
        if orcid:
            person["schema:identifier"] = orcid

        result.append(person)
    return result


def _reverse_contributors(ada_contributors: list) -> List[Dict[str, Any]]:
    """ADA ``contributors[]`` -> ``schema:contributor`` JSON-LD."""
    result = []
    for c in ada_contributors:
        ne = c.get("nameEntity") or c.get("name_entity") or {}
        person: Dict[str, Any] = {"@type": "schema:Person"}

        full_name = ne.get("fullName") or ne.get("full_name", "")
        if full_name:
            person["schema:name"] = full_name

        given = ne.get("givenName") or ne.get("given_name", "")
        if given:
            person["schema:givenName"] = given

        family = ne.get("familyName") or ne.get("family_name", "")
        if family:
            person["schema:familyName"] = family

        contributor_type = c.get("contributorType") or c.get("contributor_type", "")
        if contributor_type:
            # Wrap in a Role
            entry: Dict[str, Any] = {
                "@type": "schema:Role",
                "schema:roleName": contributor_type,
                "schema:contributor": person,
            }
            result.append(entry)
        else:
            result.append(person)
    return result


def _reverse_funding(ada_funding: list) -> List[Dict[str, Any]]:
    """ADA ``funding[]`` -> ``schema:funding`` JSON-LD."""
    result = []
    for f in ada_funding:
        grant: Dict[str, Any] = {"@type": "schema:MonetaryGrant"}

        funder = f.get("funder", {})
        funder_name = funder.get("name", "") if isinstance(funder, dict) else str(funder)
        if funder_name:
            grant["schema:funder"] = {"@type": "schema:Organization", "schema:name": funder_name}

        award_num = f.get("awardNumber") or f.get("award_number", "")
        if award_num:
            grant["schema:identifier"] = award_num

        award_title = f.get("awardTitle") or f.get("award_title", "")
        if award_title:
            grant["schema:name"] = award_title

        result.append(grant)
    return result


def _reverse_licenses(ada_licenses: list) -> List[Dict[str, Any]]:
    """ADA ``licenses[]`` -> ``schema:license`` JSON-LD."""
    result = []
    for lic in ada_licenses:
        if isinstance(lic, str):
            result.append({"@type": "schema:CreativeWork", "schema:name": lic})
        elif isinstance(lic, dict):
            entry: Dict[str, Any] = {"@type": "schema:CreativeWork"}
            if lic.get("name"):
                entry["schema:name"] = lic["name"]
            if lic.get("url"):
                entry["schema:url"] = lic["url"]
            if lic.get("description"):
                entry["schema:description"] = lic["description"]
            result.append(entry)
    return result


def ada_to_jsonld(ada_record: dict) -> dict:
    """
    Reverse-translate an ADA API record into a schema:-prefixed JSON-LD document.

    This is the inverse of ``jsonld_to_ada()``.  It maps ADA camelCase fields
    back to JSON-LD with ``schema:`` prefixes.

    Parameters
    ----------
    ada_record : dict
        The JSON response from ``GET /api/record/{doi}``.

    Returns
    -------
    dict
        A JSON-LD document suitable for loading into the metadata form.
    """
    jsonld: Dict[str, Any] = {
        "@context": {"schema": "http://schema.org/"},
        "@type": "schema:Dataset",
    }

    # Scalar fields
    title = ada_record.get("title", "")
    if title:
        jsonld["schema:name"] = title

    description = ada_record.get("description", "")
    if description:
        jsonld["schema:description"] = description

    specific_type = ada_record.get("specificType") or ada_record.get("specific_type", "")
    if specific_type:
        jsonld["schema:additionalType"] = specific_type

    pub_date = ada_record.get("publicationDate") or ada_record.get("publication_date", "")
    if pub_date:
        jsonld["schema:datePublished"] = pub_date

    doi = ada_record.get("doi", "")
    if doi:
        jsonld["schema:identifier"] = {
            "@type": "schema:PropertyValue",
            "schema:propertyID": "DOI",
            "schema:value": doi,
        }

    # Nested fields
    creators = ada_record.get("creators", [])
    if creators:
        jsonld["schema:creator"] = _reverse_creators(creators)

    contributors = ada_record.get("contributors", [])
    if contributors:
        jsonld["schema:contributor"] = _reverse_contributors(contributors)

    funding = ada_record.get("funding", [])
    if funding:
        jsonld["schema:funding"] = _reverse_funding(funding)

    licenses = ada_record.get("licenses", [])
    if licenses:
        jsonld["schema:license"] = _reverse_licenses(licenses)

    # Files -> distribution
    files = ada_record.get("files", [])
    if files:
        distributions = []
        for f in files:
            dist: Dict[str, Any] = {"@type": "schema:DataDownload"}
            name = f.get("name", "")
            if name:
                dist["schema:name"] = name
            ext = f.get("extension", "")
            if ext:
                dist["schema:encodingFormat"] = ext
            distributions.append(dist)
        jsonld["schema:distribution"] = distributions

    return jsonld
