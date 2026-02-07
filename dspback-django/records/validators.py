"""JSON Schema validation for record JSON-LD payloads."""

from typing import List

from jsonschema import Draft7Validator, Draft202012Validator


def validate_record(jsonld: dict, profile_schema: dict) -> List[str]:
    """Validate *jsonld* against *profile_schema*.

    Detects JSON Schema draft from ``$schema`` and uses the appropriate
    validator class.  Returns a list of human-readable error messages
    (empty if valid).
    """
    schema_uri = profile_schema.get("$schema", "")

    if "draft-07" in schema_uri or "draft/7" in schema_uri:
        validator_cls = Draft7Validator
    else:
        # Default to 2020-12 for modern schemas
        validator_cls = Draft202012Validator

    validator = validator_cls(profile_schema)
    errors = sorted(validator.iter_errors(jsonld), key=lambda e: list(e.absolute_path))
    return [
        f"{'.'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}"
        for e in errors
    ]
