"""JSON-LD field extraction and import helpers."""

import logging
import uuid
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


def extract_indexed_fields(jsonld: dict) -> dict:
    """Extract title, creators, and identifier from a JSON-LD document.

    Returns:
        dict with keys: title, creators, identifier
    """
    # Title: schema:name
    title = jsonld.get("schema:name", "")

    # Creators: schema:creator.@list[].schema:name
    creators: List[str] = []
    creator = jsonld.get("schema:creator", {})
    if isinstance(creator, dict):
        creator_list = creator.get("@list", [])
    elif isinstance(creator, list):
        creator_list = creator
    else:
        creator_list = []
    for person in creator_list:
        if isinstance(person, dict):
            name = person.get("schema:name")
            if name:
                creators.append(name)

    # Identifier: @id or schema:identifier, fallback to UUID
    identifier = jsonld.get("@id") or jsonld.get("schema:identifier") or ""

    return {
        "title": title,
        "creators": creators,
        "identifier": identifier,
    }


def _extract_identifier(entity: dict) -> dict:
    """Extract identifier fields from a JSON-LD entity."""
    ident = entity.get("schema:identifier", {})
    if isinstance(ident, dict):
        return {
            "identifier_type": ident.get("schema:propertyID", ""),
            "identifier_value": ident.get("schema:value", ""),
            "identifier_url": ident.get("schema:url", ""),
        }
    return {"identifier_type": "", "identifier_value": "", "identifier_url": ""}


def _extract_person(person: dict) -> Optional[dict]:
    """Extract a person record from a JSON-LD person object."""
    if not isinstance(person, dict):
        return None
    name = person.get("schema:name", "")
    if not name:
        return None

    result = {"name": name, **_extract_identifier(person)}

    # Extract affiliation
    affil = person.get("schema:affiliation", {})
    if isinstance(affil, dict):
        result["affiliation_name"] = affil.get("schema:name", "")
        affil_id = _extract_identifier(affil)
        result["affiliation_identifier_type"] = affil_id["identifier_type"]
        result["affiliation_identifier_value"] = affil_id["identifier_value"]
        result["affiliation_identifier_url"] = affil_id["identifier_url"]
    else:
        result["affiliation_name"] = ""
        result["affiliation_identifier_type"] = ""
        result["affiliation_identifier_value"] = ""
        result["affiliation_identifier_url"] = ""

    return result


def _extract_org(org: dict) -> Optional[dict]:
    """Extract an organization record from a JSON-LD organization object."""
    if not isinstance(org, dict):
        return None
    name = org.get("schema:name", "")
    if not name:
        return None
    return {"name": name, **_extract_identifier(org)}


def extract_known_entities(jsonld: dict) -> dict:
    """Extract person and organization entities from a JSON-LD document.

    Returns:
        dict with keys: persons (list of dicts), organizations (list of dicts)
    """
    persons: List[dict] = []
    organizations: List[dict] = []

    # schema:creator.@list[]
    creator = jsonld.get("schema:creator", {})
    if isinstance(creator, dict):
        creator_list = creator.get("@list", [])
    elif isinstance(creator, list):
        creator_list = creator
    else:
        creator_list = []
    for person in creator_list:
        extracted = _extract_person(person)
        if extracted:
            persons.append(extracted)
        # Also extract affiliation as an org
        if isinstance(person, dict):
            affil = person.get("schema:affiliation")
            if affil:
                org = _extract_org(affil)
                if org:
                    organizations.append(org)

    # schema:contributor[]
    contributors = jsonld.get("schema:contributor", [])
    if isinstance(contributors, dict):
        contributors = [contributors]
    if isinstance(contributors, list):
        for person in contributors:
            extracted = _extract_person(person)
            if extracted:
                persons.append(extracted)
            if isinstance(person, dict):
                affil = person.get("schema:affiliation")
                if affil:
                    org = _extract_org(affil)
                    if org:
                        organizations.append(org)

    # schema:subjectOf.schema:maintainer
    subject_of = jsonld.get("schema:subjectOf", {})
    if isinstance(subject_of, dict):
        maintainer = subject_of.get("schema:maintainer")
        if isinstance(maintainer, dict):
            extracted = _extract_person(maintainer)
            if extracted:
                persons.append(extracted)
        elif isinstance(maintainer, list):
            for person in maintainer:
                extracted = _extract_person(person)
                if extracted:
                    persons.append(extracted)

    # schema:publisher (organization)
    publisher = jsonld.get("schema:publisher")
    if publisher:
        org = _extract_org(publisher)
        if org:
            organizations.append(org)

    # schema:provider[] (organizations)
    providers = jsonld.get("schema:provider", [])
    if isinstance(providers, dict):
        providers = [providers]
    if isinstance(providers, list):
        for prov in providers:
            org = _extract_org(prov)
            if org:
                organizations.append(org)

    return {"persons": persons, "organizations": organizations}


def upsert_known_entities(jsonld: dict) -> None:
    """Extract entities from JSON-LD and upsert into KnownPerson/KnownOrganization."""
    from records.models import KnownOrganization, KnownPerson

    entities = extract_known_entities(jsonld)

    for person_data in entities["persons"]:
        try:
            KnownPerson.objects.update_or_create(
                name=person_data["name"],
                identifier_value=person_data["identifier_value"],
                defaults={
                    "identifier_type": person_data["identifier_type"],
                    "identifier_url": person_data["identifier_url"],
                    "affiliation_name": person_data.get("affiliation_name", ""),
                    "affiliation_identifier_type": person_data.get("affiliation_identifier_type", ""),
                    "affiliation_identifier_value": person_data.get("affiliation_identifier_value", ""),
                    "affiliation_identifier_url": person_data.get("affiliation_identifier_url", ""),
                },
            )
        except Exception:
            logger.warning("Failed to upsert KnownPerson: %s", person_data["name"])

    for org_data in entities["organizations"]:
        try:
            KnownOrganization.objects.update_or_create(
                name=org_data["name"],
                identifier_value=org_data["identifier_value"],
                defaults={
                    "identifier_type": org_data["identifier_type"],
                    "identifier_url": org_data["identifier_url"],
                },
            )
        except Exception:
            logger.warning("Failed to upsert KnownOrganization: %s", org_data["name"])


def fetch_jsonld_from_url(url: str, timeout: int = 30) -> dict:
    """Fetch a JSON-LD document from *url*.

    Tries content negotiation for JSON-LD first, falls back to plain JSON.
    Raises ``ValueError`` on failure.
    """
    headers = {"Accept": "application/ld+json, application/json"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        raise ValueError(f"Failed to fetch URL (HTTP {resp.status_code})")
    try:
        return resp.json()
    except ValueError:
        raise ValueError("Response is not valid JSON")
