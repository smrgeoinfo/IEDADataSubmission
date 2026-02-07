"""JSON-LD field extraction and import helpers."""

import uuid
from typing import Dict, List, Optional

import requests


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
