"""Inject layout configs into UISchema and defaults into schema at serve time."""

import copy

# ---------------------------------------------------------------------------
# Person / Organization vocabulary injection (DISABLED)
#
# CzForm's VocabularyArrayRenderer replaces the normal array control entirely,
# allowing only selection from search results — there is no "Add new" button.
# Until CzForm adds a "create manually" option alongside search, vocabulary
# injection is disabled.  The constants and API endpoints remain so we can
# re-enable this once CzForm is enhanced.
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

# Set to True to re-enable vocabulary autocomplete on person/org controls.
VOCABULARY_ENABLED = False

# ---------------------------------------------------------------------------
# MIME type options from adaFileExtensions lookup table
# ---------------------------------------------------------------------------

MIME_TYPE_OPTIONS = [
    {"const": "application/json", "title": ".json - JSON (application/json)"},
    {"const": "application/ld+json", "title": ".jsonld - JSON-LD (application/ld+json)"},
    {"const": "application/pdf", "title": ".pdf - PDF Document (application/pdf)"},
    {"const": "application/rtf", "title": ".rtf - Rich Text Format (application/rtf)"},
    {"const": "application/vnd.ms-excel", "title": ".xls - Excel Spreadsheet (application/vnd.ms-excel)"},
    {"const": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "title": ".xlsx - Excel Spreadsheet (application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)"},
    {"const": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "title": ".docx - Word Document (application/vnd.openxmlformats-officedocument.wordprocessingml.document)"},
    {"const": "application/x-hdf5", "title": ".hdf5 - HDF5 (application/x-hdf5)"},
    {"const": "application/x-netcdf", "title": ".nc - NetCDF (application/x-netcdf)"},
    {"const": "application/xml", "title": ".xml - XML (application/xml)"},
    {"const": "application/yaml", "title": ".yaml - YAML (application/yaml)"},
    {"const": "application/zip", "title": ".zip - ZIP Archive (application/zip)"},
    {"const": "image/bmp", "title": ".bmp - Bitmap Image (image/bmp)"},
    {"const": "image/jpeg", "title": ".jpg - JPEG Image (image/jpeg)"},
    {"const": "image/png", "title": ".png - PNG Image (image/png)"},
    {"const": "image/svg+xml", "title": ".svg - SVG Image (image/svg+xml)"},
    {"const": "image/tiff", "title": ".tif - TIFF Image (image/tiff)"},
    {"const": "model/obj", "title": ".obj - 3D Object (model/obj)"},
    {"const": "model/stl", "title": ".stl - Stereolithography (model/stl)"},
    {"const": "text/csv", "title": ".csv - Comma Separated Values (text/csv)"},
    {"const": "text/html", "title": ".html - HTML (text/html)"},
    {"const": "text/markdown", "title": ".md - Markdown (text/markdown)"},
    {"const": "text/plain", "title": ".txt - Plain Text (text/plain)"},
    {"const": "text/tab-separated-values", "title": ".tsv - Tab Separated Values (text/tab-separated-values)"},
    {"const": "video/mp4", "title": ".mp4 - MP4 Video (video/mp4)"},
    {"const": "video/quicktime", "title": ".mov - QuickTime Video (video/quicktime)"},
]

# Flat enum list of media type strings for schema injection.
# CzForm doesn't render oneOf on primitive strings as a searchable dropdown,
# so we use enum instead.  MIME_TYPE_OPTIONS is kept for reference/tests.
MIME_TYPE_ENUM = [opt["const"] for opt in MIME_TYPE_OPTIONS]

# ---------------------------------------------------------------------------
# Variable panel progressive disclosure
# ---------------------------------------------------------------------------

VARIABLE_MEASURED_SCOPES = {
    "#/properties/schema:variableMeasured",
}

# Detail layout for DefinedTerm items inside propertyID array.
# Excludes @type (which has a schema default and doesn't need user input).
DEFINED_TERM_DETAIL = {
    "type": "VerticalLayout",
    "elements": [
        {"type": "Control", "scope": "#/properties/schema:name", "label": "Name"},
        {"type": "Control", "scope": "#/properties/schema:identifier", "label": "Identifier"},
        {
            "type": "Control",
            "scope": "#/properties/schema:inDefinedTermSet",
            "label": "Defined Term Set",
        },
        {"type": "Control", "scope": "#/properties/schema:termCode", "label": "Term Code"},
    ],
}

# Detail layout for measurementTechnique (single DefinedTerm object).
# Excludes @type — only shows schema:name.
MEASUREMENT_TECHNIQUE_DETAIL = {
    "type": "VerticalLayout",
    "elements": [
        {"type": "Control", "scope": "#/properties/schema:name", "label": "Name"},
    ],
}

# Variable detail with advanced toggle:
# - Basic fields: name, propertyID, description
# - _showAdvanced checkbox
# - Advanced group with SHOW rule (shown when toggle is on OR any advanced field has data)
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
            "options": {
                "detail": DEFINED_TERM_DETAIL,
            },
        },
        {
            "type": "Control",
            "scope": "#/properties/schema:description",
            "label": "Description",
            "options": {"multi": True},
        },
        {
            "type": "Control",
            "scope": "#/properties/_showAdvanced",
            "label": "Show Advanced Options",
        },
        {
            "type": "Group",
            "label": "Advanced",
            "rule": {
                "effect": "SHOW",
                "condition": {
                    "type": "OR",
                    "conditions": [
                        {
                            "scope": "#/properties/_showAdvanced",
                            "schema": {"const": True},
                        },
                        {
                            "scope": "#/properties/schema:measurementTechnique",
                            "schema": {},
                            "failWhenUndefined": True,
                        },
                        {
                            "scope": "#/properties/schema:unitText",
                            "schema": {"minLength": 1},
                            "failWhenUndefined": True,
                        },
                        {
                            "scope": "#/properties/schema:unitCode",
                            "schema": {"minLength": 1},
                            "failWhenUndefined": True,
                        },
                        {
                            "scope": "#/properties/schema:minValue",
                            "schema": {"type": "number"},
                            "failWhenUndefined": True,
                        },
                        {
                            "scope": "#/properties/schema:maxValue",
                            "schema": {"type": "number"},
                            "failWhenUndefined": True,
                        },
                    ],
                },
            },
            "elements": [
                {
                    "type": "Control",
                    "scope": "#/properties/schema:measurementTechnique",
                    "label": "Measurement Technique",
                    "options": {
                        "detail": MEASUREMENT_TECHNIQUE_DETAIL,
                    },
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
# Distribution detail with type selector + WebAPI support
# ---------------------------------------------------------------------------

DISTRIBUTION_SCOPES = {
    "#/properties/schema:distribution",
}

# Detail layout for hasPart items (files within archives).
HAS_PART_DETAIL = {
    "type": "VerticalLayout",
    "elements": [
        {"type": "Control", "scope": "#/properties/schema:name", "label": "File Name"},
        {"type": "Control", "scope": "#/properties/schema:description", "label": "Description"},
        {
            "type": "Control",
            "scope": "#/properties/schema:encodingFormat",
            "label": "MIME Type",
        },
    ],
}

DISTRIBUTION_DETAIL = {
    "type": "VerticalLayout",
    "elements": [
        {
            "type": "Control",
            "scope": "#/properties/_distributionType",
            "label": "Distribution Type",
        },
        {
            "type": "Control",
            "scope": "#/properties/schema:name",
            "label": "Name",
        },
        {
            "type": "Control",
            "scope": "#/properties/schema:description",
            "label": "Description",
        },
        {
            "type": "Control",
            "scope": "#/properties/schema:contentUrl",
            "label": "Content URL",
            "rule": {
                "effect": "SHOW",
                "condition": {
                    "scope": "#/properties/_distributionType",
                    "schema": {"const": "Data Download"},
                },
            },
        },
        {
            "type": "Control",
            "scope": "#/properties/schema:encodingFormat",
            "label": "MIME Type",
            "rule": {
                "effect": "SHOW",
                "condition": {
                    "scope": "#/properties/_distributionType",
                    "schema": {"const": "Data Download"},
                },
            },
        },
        {
            "type": "Control",
            "scope": "#/properties/schema:hasPart",
            "label": "Archive Contents",
            "options": {
                "elementLabelProp": "schema:name",
                "detail": HAS_PART_DETAIL,
            },
            "rule": {
                "effect": "SHOW",
                "condition": {
                    "type": "AND",
                    "conditions": [
                        {
                            "scope": "#/properties/_distributionType",
                            "schema": {"const": "Data Download"},
                        },
                        {
                            "scope": "#/properties/schema:encodingFormat",
                            "schema": {"contains": {"const": "application/zip"}},
                        },
                    ],
                },
            },
        },
        {
            "type": "Control",
            "scope": "#/properties/schema:serviceType",
            "label": "Service Type",
            "rule": {
                "effect": "SHOW",
                "condition": {
                    "scope": "#/properties/_distributionType",
                    "schema": {"const": "Web API"},
                },
            },
        },
        {
            "type": "Control",
            "scope": "#/properties/schema:documentation",
            "label": "Documentation URL",
            "rule": {
                "effect": "SHOW",
                "condition": {
                    "scope": "#/properties/_distributionType",
                    "schema": {"const": "Web API"},
                },
            },
        },
    ],
}


# ---------------------------------------------------------------------------
# Schema defaults injection
# ---------------------------------------------------------------------------

def inject_schema_defaults(schema):
    """Add default values and injected properties at serve time.

    - variableMeasured items: @type default, _showAdvanced boolean
    - distribution items: _distributionType enum, WebAPI properties
    - encodingFormat: enum for MIME type selection
    """
    result = copy.deepcopy(schema)

    # --- variableMeasured defaults ---
    var_measured = (
        result.get("properties", {}).get("schema:variableMeasured", {})
    )
    items = var_measured.get("items", {})
    items_props = items.get("properties", {})

    at_type = items_props.get("@type", {})
    if isinstance(at_type, dict) and "default" not in at_type and at_type.get("type") == "array":
        at_type["default"] = ["schema:PropertyValue"]

    # Inject _showAdvanced boolean for advanced toggle
    if items_props:
        items_props["_showAdvanced"] = {"type": "boolean", "default": False}

    # --- distribution defaults ---
    distribution = result.get("properties", {}).get("schema:distribution", {})
    dist_items = distribution.get("items", {})
    dist_props = dist_items.get("properties", {})

    if dist_props:
        # Type selector field
        dist_props["_distributionType"] = {
            "type": "string",
            "enum": ["Data Download", "Web API"],
            "default": "Data Download",
        }
        # WebAPI properties (not in OGC BB schema, injected at serve time)
        dist_props.setdefault("schema:serviceType", {"type": "string"})
        dist_props.setdefault("schema:documentation", {"type": "string", "format": "uri"})

        # MIME type enum on distribution encodingFormat
        enc_fmt = dist_props.get("schema:encodingFormat", {})
        if isinstance(enc_fmt, dict) and enc_fmt.get("type") == "array":
            enc_fmt_items = enc_fmt.get("items", {})
            if isinstance(enc_fmt_items, dict):
                enc_fmt_items["enum"] = MIME_TYPE_ENUM

        # MIME type enum on hasPart items' encodingFormat
        has_part = dist_props.get("schema:hasPart", {})
        hp_items = has_part.get("items", {})
        hp_props = hp_items.get("properties", {})
        hp_enc_fmt = hp_props.get("schema:encodingFormat", {})
        if isinstance(hp_enc_fmt, dict) and hp_enc_fmt.get("type") == "array":
            hp_enc_items = hp_enc_fmt.get("items", {})
            if isinstance(hp_enc_items, dict):
                hp_enc_items["enum"] = MIME_TYPE_ENUM

    return result


# ---------------------------------------------------------------------------
# UISchema injection
# ---------------------------------------------------------------------------

def inject_uischema(uischema):
    """Deep-copy uischema and inject layout configs on matching controls."""
    result = copy.deepcopy(uischema)
    _walk(result)
    return result


def _walk(node):
    """Recursively walk the UISchema tree and inject configs on matching controls."""
    if not isinstance(node, dict):
        return

    scope = node.get("scope", "")

    # --- Person/org vocabulary injection (disabled) ---
    if VOCABULARY_ENABLED:
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
    if scope in VARIABLE_MEASURED_SCOPES:
        options = node.setdefault("options", {})
        options["elementLabelProp"] = "schema:name"
        options["detail"] = copy.deepcopy(VARIABLE_DETAIL)

    # --- Distribution detail with type selector ---
    if scope in DISTRIBUTION_SCOPES:
        options = node.setdefault("options", {})
        options["elementLabelProp"] = "schema:name"
        options["detail"] = copy.deepcopy(DISTRIBUTION_DETAIL)

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
