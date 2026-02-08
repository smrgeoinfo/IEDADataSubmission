"""Inject vocabulary autocomplete and layout configs into UISchema at serve time."""

import copy

# ---------------------------------------------------------------------------
# Person / Organization vocabulary injection
# ---------------------------------------------------------------------------

PERSON_SCOPES = {
    "#/properties/schema:creator/properties/@list",
    "#/properties/schema:contributor",
    "#/properties/schema:subjectOf/properties/schema:maintainer",
}

ORG_ARRAY_SCOPES = {
    "#/properties/schema:provider",
}

ORG_NAME_SCOPES = {
    "#/properties/schema:publisher/properties/schema:name",
}

PERSON_VOCABULARY = {
    "jsonUrl": "/api/catalog/persons/",
    "queryParams": {"search": "q"},
    "items": "results",
    "value": {
        "schema:name": {"contents": "schema:name"},
        "schema:identifier": {"contents": "schema:identifier", "hidden": True},
        "schema:affiliation": {"contents": "schema:affiliation", "hidden": True},
    },
}

ORG_VOCABULARY = {
    "jsonUrl": "/api/catalog/organizations/",
    "queryParams": {"search": "q"},
    "items": "results",
    "value": {
        "schema:name": {"contents": "schema:name"},
        "schema:identifier": {"contents": "schema:identifier", "hidden": True},
    },
}

# ---------------------------------------------------------------------------
# Variable panel progressive disclosure
# ---------------------------------------------------------------------------

VARIABLE_MEASURED_SCOPES = {
    "#/properties/schema:variableMeasured",
}

# Advanced fields shown inside a collapsible "Advanced" group.
# expandWhenPopulated tells CzForm to auto-open the group when any child
# control already has data (requires CzForm support).
VARIABLE_DETAIL = {
    "type": "VerticalLayout",
    "elements": [
        {
            "type": "Control",
            "scope": "#/properties/schema:name",
            "label": "Name",
        },
        {
            "type": "Control",
            "scope": "#/properties/schema:propertyID",
            "label": "Property ID",
        },
        {
            "type": "Control",
            "scope": "#/properties/schema:description",
            "label": "Description",
            "options": {"multi": True},
        },
        {
            "type": "Group",
            "label": "Advanced",
            "options": {"collapsed": True, "expandWhenPopulated": True},
            "elements": [
                {
                    "type": "Control",
                    "scope": "#/properties/schema:measurementTechnique",
                    "label": "Measurement Technique",
                },
                {
                    "type": "HorizontalLayout",
                    "elements": [
                        {
                            "type": "Control",
                            "scope": "#/properties/schema:unitText",
                            "label": "Unit Text",
                        },
                        {
                            "type": "Control",
                            "scope": "#/properties/schema:unitCode",
                            "label": "Unit Code",
                        },
                    ],
                },
                {
                    "type": "HorizontalLayout",
                    "elements": [
                        {
                            "type": "Control",
                            "scope": "#/properties/schema:minValue",
                            "label": "Min Value",
                        },
                        {
                            "type": "Control",
                            "scope": "#/properties/schema:maxValue",
                            "label": "Max Value",
                        },
                    ],
                },
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def inject_vocabulary(uischema):
    """Deep-copy uischema and inject vocabulary and layout configs on matching controls."""
    result = copy.deepcopy(uischema)
    _walk(result)
    return result


def _walk(node):
    """Recursively walk the UISchema tree and inject configs on matching controls."""
    if not isinstance(node, dict):
        return

    scope = node.get("scope", "")

    # --- Person/org vocabulary injection ---
    if scope in PERSON_SCOPES:
        options = node.setdefault("options", {})
        options["vocabulary"] = copy.deepcopy(PERSON_VOCABULARY)
    elif scope in ORG_ARRAY_SCOPES:
        options = node.setdefault("options", {})
        options["vocabulary"] = copy.deepcopy(ORG_VOCABULARY)
    elif scope in ORG_NAME_SCOPES:
        options = node.setdefault("options", {})
        options["vocabulary"] = copy.deepcopy(ORG_VOCABULARY)

    # --- Variable panel progressive disclosure ---
    elif scope in VARIABLE_MEASURED_SCOPES:
        options = node.setdefault("options", {})
        options["elementLabelProp"] = "schema:name"
        options["detail"] = copy.deepcopy(VARIABLE_DETAIL)

    # Recurse into child nodes
    for child in node.get("elements", []):
        _walk(child)

    # Recurse into detail (used by array controls)
    detail = node.get("detail")
    if isinstance(detail, dict):
        _walk(detail)

    # Recurse into options.detail
    options = node.get("options")
    if isinstance(options, dict):
        options_detail = options.get("detail")
        if isinstance(options_detail, dict):
            _walk(options_detail)
