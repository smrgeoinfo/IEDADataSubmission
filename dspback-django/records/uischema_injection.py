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

MAINTAINER_SCOPES = {
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
# MIME type category groupings for file-type-specific field display
# ---------------------------------------------------------------------------

IMAGE_MIMES = ["image/jpeg", "image/png", "image/tiff", "image/bmp", "image/svg+xml"]
TABULAR_MIMES = ["text/csv", "text/tab-separated-values"]
DATACUBE_MIMES = ["application/x-hdf5", "application/x-netcdf"]
DOCUMENT_MIMES = [
    "application/pdf", "text/plain", "text/html", "text/markdown",
    "application/rtf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]
ARCHIVE_MIMES = ["application/zip"]
STRUCTURED_DATA_MIMES = [
    "application/json", "application/ld+json", "application/xml", "application/yaml",
]
SPREADSHEET_MIMES = [
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
]
MODEL_MIMES = ["model/obj", "model/stl"]
VIDEO_MIMES = ["video/mp4", "video/quicktime"]

# ---------------------------------------------------------------------------
# Per-category componentType enum values (from building block schemas)
# ---------------------------------------------------------------------------

# image + imageMap building blocks — shown when IMAGE_MIMES selected
IMAGE_COMPONENT_TYPES = [
    # image building block
    "ada:AIVAImage", "ada:EMPAImage", "ada:LITImage", "ada:STEMImage",
    "ada:TEMImage", "ada:TEMPatternsImage", "ada:UVFMImage", "ada:VLMImage",
    "ada:SEMEBSDGrainImage", "ada:SEMEDSElementalMap", "ada:SEMHRCLImage",
    "ada:SEMImageCollection", "ada:TEMEDSImageCollection", "ada:NanoSIMSImage",
    "ada:XANESImageStack", "ada:XANESStackOverviewImage",
    "ada:XRDDiffractionPattern", "ada:ShapeModelImage",
    # imageMap building block (additional unique types)
    "ada:basemap", "ada:supplementalBasemap", "ada:L2MSOverviewImage",
    "ada:NanoIRMap", "ada:SEMEBSDGrainImageMap", "ada:SEMHRCLMap",
    "ada:SEMImageMap", "ada:NanoSIMSMap", "ada:XANESimage", "ada:VNMIROverviewImage",
    "ada:EMPAQEATabular", "ada:EMPAImageCollection",
]

# tabularData building block — shown when TABULAR_MIMES selected
TABULAR_COMPONENT_TYPES = [
    "ada:AMSRawData", "ada:AMSProcessedData",
    "ada:DSCResultsTabular", "ada:DSCHeatTabular",
    "ada:EAIRMSCollection",
    "ada:EMPAQEATabular",
    "ada:FTICRMSTabular",
    "ada:GPYCProcessedTabular", "ada:GPYCRawTabular",
    "ada:HRICPMSProcessed", "ada:HRICPMSRaw",
    "ada:ICPOESIntermediateTabular", "ada:ICPOESProcessedTabular", "ada:ICPOESRawTabular",
    "ada:ICTabular",
    "ada:LAFProcessed", "ada:LAFRaw",
    "ada:MCICPMSTabular",
    "ada:NanoIRBackground",
    "ada:NanoSIMSTabular",
    "ada:NGNSMSRaw", "ada:NGNSMSProcessed",
    "ada:PSFDTabular",
    "ada:QICPMSProcessedTabular", "ada:QICPMSRawTabular",
    "ada:RAMANRawTabular",
    "ada:RITOFNGMSTabular",
    "ada:SEMEDSPointData", "ada:SIMSTabular",
    "ada:STEMEDSTabular", "ada:STEMEELSTabular",
    "ada:SVRUECTabular",
    "ada:VNMIRSpectralPoint",
    "ada:XANESRawTabular", "ada:XANESProcessedTabular",
    "ada:XRDTabular",
]

# dataCube building block — shown when DATACUBE_MIMES selected
DATACUBE_COMPONENT_TYPES = [
    "ada:FTICRMSCube",
    "ada:GCMSCollection", "ada:GCMSCube",
    "ada:L2MSCube",
    "ada:LCMSCollection",
    "ada:SEMEBSDGrainImageMapCube", "ada:SEMEDSElementalMapsCube",
    "ada:SEMEDSPointDataCube", "ada:SEMHRCLCube",
    "ada:STEMEDSCube", "ada:STEMEDSTomo", "ada:STEMEELSCube",
    "ada:VNMIRSpectralMap",
]

# document building block — shown when DOCUMENT_MIMES selected
DOCUMENT_COMPONENT_TYPES = [
    "ada:ARGTDocument",
    "ada:calibrationFile", "ada:contextVideo",
    "ada:logFile", "ada:methodDescription",
    "ada:peaks", "ada:processingDescription",
    "ada:QRISCalibrationFile",
    "ada:samplePreparation", "ada:shapefiles",
]

# Generic types available in every category dropdown
GENERIC_COMPONENT_TYPES = [
    "ada:analysisLocation", "ada:annotatedProduct", "ada:contextPhotography",
    "ada:areaOfInterest", "ada:instrumentMetadata", "ada:other",
    "ada:plot", "ada:quickLook", "ada:report", "ada:visImage",
]

# ---------------------------------------------------------------------------
# Per-profile measurement detail controls
# ---------------------------------------------------------------------------

def _ct_ctrl(prop, label):
    """Shorthand for a componentType property control."""
    return {
        "type": "Control",
        "scope": f"#/properties/fileDetail/properties/componentType/properties/{prop}",
        "label": label,
    }

PROFILE_MEASUREMENT_CONTROLS = {
    "adaVNMIR": {
        "label": "VNMIR Measurement Details",
        "elements": [
            {"type": "HorizontalLayout", "elements": [
                _ct_ctrl("detector", "Detector"),
                _ct_ctrl("beamsplitter", "Beamsplitter"),
            ]},
            {"type": "HorizontalLayout", "elements": [
                _ct_ctrl("measurement", "Measurement"),
                _ct_ctrl("measurementEnvironment", "Measurement Environment"),
            ]},
            {"type": "HorizontalLayout", "elements": [
                _ct_ctrl("spectralRangeMin", "Spectral Range Min"),
                _ct_ctrl("spectralRangeMax", "Spectral Range Max"),
            ]},
            {"type": "HorizontalLayout", "elements": [
                _ct_ctrl("spectralResolution", "Spectral Resolution"),
                _ct_ctrl("spectralSampling", "Spectral Sampling"),
            ]},
            {"type": "HorizontalLayout", "elements": [
                _ct_ctrl("spotSize", "Spot Size"),
                _ct_ctrl("numberOfScans", "Number of Scans"),
            ]},
            {"type": "HorizontalLayout", "elements": [
                _ct_ctrl("emissionAngle", "Emission Angle"),
                _ct_ctrl("incidenceAngle", "Incidence Angle"),
                _ct_ctrl("phaseAngle", "Phase Angle"),
            ]},
            {"type": "HorizontalLayout", "elements": [
                _ct_ctrl("sampleTemperature", "Sample Temperature"),
                _ct_ctrl("samplePreparation", "Sample Preparation"),
            ]},
            {"type": "HorizontalLayout", "elements": [
                _ct_ctrl("sampleHeated", "Sample Heated"),
                _ct_ctrl("vacuumExposedSample", "Vacuum Exposed Sample"),
            ]},
            {"type": "HorizontalLayout", "elements": [
                _ct_ctrl("environmentalPressure", "Environmental Pressure"),
                _ct_ctrl("uncertaintyNoise", "Uncertainty Noise"),
            ]},
            {"type": "HorizontalLayout", "elements": [
                _ct_ctrl("eMaxFitRegionMin", "E-Max Fit Region Min"),
                _ct_ctrl("eMaxFitRegionMax", "E-Max Fit Region Max"),
                _ct_ctrl("emissivityMaximum", "Emissivity Maximum"),
            ]},
            _ct_ctrl("calibrationStandards", "Calibration Standards"),
            _ct_ctrl("comments", "Comments"),
        ],
    },
    "adaEMPA": {
        "label": "EMPA Measurement Details",
        "elements": [
            {"type": "HorizontalLayout", "elements": [
                _ct_ctrl("spectrometersUsed", "Spectrometers Used"),
                _ct_ctrl("signalUsed", "Signal Used"),
            ]},
        ],
    },
    "adaXRD": {
        "label": "XRD Measurement Details",
        "elements": [
            {"type": "HorizontalLayout", "elements": [
                _ct_ctrl("geometry", "Geometry"),
                _ct_ctrl("sampleMount", "Sample Mount"),
            ]},
            {"type": "HorizontalLayout", "elements": [
                _ct_ctrl("stepSize", "Step Size"),
                _ct_ctrl("timePerStep", "Time Per Step"),
                _ct_ctrl("wavelength", "Wavelength"),
            ]},
        ],
    },
}


def _inject_measurement_group(detail, profile_name):
    """Insert technique-specific measurement controls into detail groups."""
    config = PROFILE_MEASUREMENT_CONTROLS.get(profile_name)
    if not config:
        return
    measurement_group = {
        "type": "Group",
        "label": config["label"],
        "elements": copy.deepcopy(config["elements"]),
    }
    _insert_after_component_type(detail.get("elements", []), measurement_group)


def _insert_after_component_type(elements, measurement_group):
    """Recursively find ComponentType controls and insert measurement group after them."""
    for element in elements:
        sub = element.get("elements", [])
        for i, el in enumerate(sub):
            scope = el.get("scope", "")
            if "ComponentType" in scope and scope.startswith("#/properties/fileDetail"):
                sub.insert(i + 1, copy.deepcopy(measurement_group))
                break  # Inserted in this group, continue to next sibling
        else:
            # No ComponentType found here — recurse into sub-elements
            _insert_after_component_type(sub, measurement_group)


# ---------------------------------------------------------------------------
# Per-profile MIME type filtering
# ---------------------------------------------------------------------------

# File type → MIME types mapping
FILE_TYPE_TO_MIMES = {
    "image": IMAGE_MIMES,
    "imageMap": IMAGE_MIMES,
    "tabularData": TABULAR_MIMES,
    "dataCube": DATACUBE_MIMES,
    "document": DOCUMENT_MIMES,
    "collection": ARCHIVE_MIMES,
    "supDocImage": IMAGE_MIMES,
    "otherFileType": MODEL_MIMES + VIDEO_MIMES,
}

# Profile → supported file types (which drive the MIME dropdown options)
# adaProduct supports all file types; technique profiles support subsets.
PROFILE_FILE_TYPES = {
    "adaProduct": "all",
    "adaEMPA": ["imageMap", "image", "tabularData", "collection", "supDocImage", "document"],
    "adaXRD": ["tabularData", "image", "document"],
    "adaICPMS": ["tabularData", "collection", "document"],
    "adaVNMIR": ["tabularData", "imageMap", "dataCube", "supDocImage", "document"],
}


def _get_profile_mime_enum(profile_name):
    """Return the filtered MIME enum for a profile, or full list if unknown.

    adaProduct and unknown/unset profiles get the complete MIME list.
    Technique profiles get a filtered list based on their supported file types,
    plus structured data formats (JSON, XML, YAML) always included.
    """
    if not profile_name or profile_name not in PROFILE_FILE_TYPES:
        return MIME_TYPE_ENUM

    file_types = PROFILE_FILE_TYPES[profile_name]

    # "all" sentinel means no filtering
    if file_types == "all":
        return MIME_TYPE_ENUM

    allowed = set()
    for ft in file_types:
        allowed.update(FILE_TYPE_TO_MIMES.get(ft, []))
    # Always include structured data formats (JSON, XML, YAML) for all profiles
    allowed.update(STRUCTURED_DATA_MIMES)

    # Return in the same order as the master list
    return [m for m in MIME_TYPE_ENUM if m in allowed]


def _mime_and_download_rule(mime_list):
    """Build an AND rule: _distributionType == 'Data Download' AND encodingFormat in mime_list."""
    return {
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
                    "schema": {"enum": mime_list},
                },
            ],
        },
    }


def _hp_mime_rule(mime_list):
    """Build a SHOW rule: hasPart encodingFormat in mime_list.

    Uses OR with individual const conditions because CzForm does not
    reliably support enum in rule conditions.
    """
    return {
        "effect": "SHOW",
        "condition": {
            "type": "OR",
            "conditions": [
                {"scope": "#/properties/schema:encodingFormat", "schema": {"const": mime}}
                for mime in mime_list
            ],
        },
    }


def _fd_ctrl(prop, label):
    """Shorthand for a fileDetail control."""
    return {
        "type": "Control",
        "scope": f"#/properties/fileDetail/properties/{prop}",
        "label": label,
    }


def _pm_ctrl(prop, label):
    """Shorthand for a physicalMapping item property control."""
    return {
        "type": "Control",
        "scope": f"#/properties/{prop}",
        "label": label,
    }


_PM_ADVANCED_GROUP = {
    "type": "Group",
    "label": "Advanced",
    "rule": {
        "effect": "SHOW",
        "condition": {
            "scope": "#/properties/_showAdvanced",
            "schema": {"const": True},
        },
    },
    "elements": [
        _pm_ctrl("cdi:format", "Format"),
        _pm_ctrl("cdi:physicalDataType", "Physical Data Type"),
        {
            "type": "HorizontalLayout",
            "elements": [
                _pm_ctrl("cdi:length", "Length"),
                _pm_ctrl("cdi:scale", "Scale"),
                _pm_ctrl("cdi:decimalPositions", "Decimal Positions"),
            ],
        },
        {
            "type": "HorizontalLayout",
            "elements": [
                _pm_ctrl("cdi:minimumLength", "Min Length"),
                _pm_ctrl("cdi:maximumLength", "Max Length"),
            ],
        },
        _pm_ctrl("cdi:nullSequence", "Null Sequence"),
        _pm_ctrl("cdi:defaultValue", "Default Value"),
        _pm_ctrl("cdi:isRequired", "Required"),
        _pm_ctrl("cdi:displayLabel", "Display Label"),
        {
            "type": "HorizontalLayout",
            "elements": [
                _pm_ctrl("cdi:defaultDecimalSeparator", "Decimal Separator"),
                _pm_ctrl("cdi:defaultDigitalGroupSeparator", "Group Separator"),
            ],
        },
    ],
}

# Detail layout for physicalMapping items (tabularData — no locator field)
PHYSICAL_MAPPING_DETAIL = {
    "type": "VerticalLayout",
    "elements": [
        {
            "type": "HorizontalLayout",
            "elements": [
                _pm_ctrl("cdi:index", "Column Index"),
                _pm_ctrl("cdi:formats_InstanceVariable", "Variable"),
            ],
        },
        {
            "type": "Control",
            "scope": "#/properties/_showAdvanced",
            "label": "Show Advanced Options",
        },
        _PM_ADVANCED_GROUP,
    ],
}

# Detail layout for physicalMapping items (dataCube — includes locator field)
PHYSICAL_MAPPING_DATACUBE_DETAIL = {
    "type": "VerticalLayout",
    "elements": [
        {
            "type": "HorizontalLayout",
            "elements": [
                _pm_ctrl("cdi:index", "Column Index"),
                _pm_ctrl("cdi:formats_InstanceVariable", "Variable"),
            ],
        },
        _pm_ctrl("cdi:locator", "Locator"),
        {
            "type": "Control",
            "scope": "#/properties/_showAdvanced",
            "label": "Show Advanced Options",
        },
        _PM_ADVANCED_GROUP,
    ],
}


# File-type Groups shown inside DISTRIBUTION_DETAIL based on MIME selection.

IMAGE_DETAIL_GROUP = {
    "type": "Group",
    "label": "Image Details",
    "rule": _mime_and_download_rule(IMAGE_MIMES),
    "elements": [
        _fd_ctrl("_imageComponentType", "Component Type"),
        _fd_ctrl("acquisitionTime", "Acquisition Time"),
        {
            "type": "HorizontalLayout",
            "elements": [
                _fd_ctrl("channel1", "Channel 1"),
                _fd_ctrl("channel2", "Channel 2"),
                _fd_ctrl("channel3", "Channel 3"),
            ],
        },
        _fd_ctrl("pixelSize", "Pixel Size"),
        _fd_ctrl("illuminationType", "Illumination Type"),
        _fd_ctrl("imageType", "Image Type"),
        {
            "type": "HorizontalLayout",
            "elements": [
                _fd_ctrl("numPixelsX", "Pixels X"),
                _fd_ctrl("numPixelsY", "Pixels Y"),
            ],
        },
        _fd_ctrl("spatialRegistration", "Spatial Registration"),
    ],
}

TABULAR_DETAIL_GROUP = {
    "type": "Group",
    "label": "Tabular Data Details",
    "rule": _mime_and_download_rule(TABULAR_MIMES),
    "elements": [
        _fd_ctrl("_tabularComponentType", "Component Type"),
        {
            "type": "HorizontalLayout",
            "elements": [
                _fd_ctrl("csvw:delimiter", "Delimiter"),
                _fd_ctrl("csvw:quoteChar", "Quote Character"),
                _fd_ctrl("csvw:commentPrefix", "Comment Prefix"),
            ],
        },
        {
            "type": "HorizontalLayout",
            "elements": [
                _fd_ctrl("csvw:header", "Has Header"),
                _fd_ctrl("csvw:headerRowCount", "Header Row Count"),
            ],
        },
        {
            "type": "HorizontalLayout",
            "elements": [
                _fd_ctrl("countRows", "Row Count"),
                _fd_ctrl("countColumns", "Column Count"),
            ],
        },
        {
            "type": "Control",
            "scope": "#/properties/fileDetail/properties/cdi:hasPhysicalMapping",
            "label": "Physical Mapping",
            "options": {
                "elementLabelProp": "cdi:formats_InstanceVariable",
                "detail": PHYSICAL_MAPPING_DETAIL,
            },
        },
    ],
}

DATACUBE_DETAIL_GROUP = {
    "type": "Group",
    "label": "Data Cube Details",
    "rule": _mime_and_download_rule(DATACUBE_MIMES),
    "elements": [
        _fd_ctrl("_dataCubeComponentType", "Component Type"),
        {
            "type": "Control",
            "scope": "#/properties/fileDetail/properties/cdi:hasPhysicalMapping",
            "label": "Physical Mapping",
            "options": {
                "elementLabelProp": "cdi:formats_InstanceVariable",
                "detail": PHYSICAL_MAPPING_DATACUBE_DETAIL,
            },
        },
        _fd_ctrl("dataComponentResource", "Data Component Resource"),
    ],
}

DOCUMENT_DETAIL_GROUP = {
    "type": "Group",
    "label": "Document Details",
    "rule": _mime_and_download_rule(DOCUMENT_MIMES),
    "elements": [
        _fd_ctrl("_documentComponentType", "Component Type"),
        _fd_ctrl("schema:version", "Version"),
        _fd_ctrl("schema:isBasedOn", "Based On"),
    ],
}

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
            "options": {"multi": True, "rows": 2, "autoGrow": True},
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
# Mirrors the distribution-level MIME-driven groups so archive contents
# get the same file-type-specific fields.
HAS_PART_DETAIL = {
    "type": "VerticalLayout",
    "elements": [
        {"type": "Control", "scope": "#/properties/schema:name", "label": "File Name"},
        {"type": "Control", "scope": "#/properties/schema:description", "label": "Description", "options": {"multi": True, "rows": 2, "autoGrow": True}},
        {
            "type": "Control",
            "scope": "#/properties/schema:encodingFormat",
            "label": "MIME Type",
        },
        # Nested archive contents (zip within zip)
        {
            "type": "Control",
            "scope": "#/properties/schema:hasPart",
            "label": "Archive Contents",
            "options": {"elementLabelProp": "schema:name"},
            "rule": {
                "effect": "SHOW",
                "condition": {
                    "scope": "#/properties/schema:encodingFormat",
                    "schema": {"const": "application/zip"},
                },
            },
        },
        # Image details
        {
            "type": "Group",
            "label": "Image Details",
            "rule": _hp_mime_rule(IMAGE_MIMES),
            "elements": [
                _fd_ctrl("_imageComponentType", "Component Type"),
                _fd_ctrl("acquisitionTime", "Acquisition Time"),
                {
                    "type": "HorizontalLayout",
                    "elements": [
                        _fd_ctrl("channel1", "Channel 1"),
                        _fd_ctrl("channel2", "Channel 2"),
                        _fd_ctrl("channel3", "Channel 3"),
                    ],
                },
                _fd_ctrl("pixelSize", "Pixel Size"),
                _fd_ctrl("illuminationType", "Illumination Type"),
                _fd_ctrl("imageType", "Image Type"),
                {
                    "type": "HorizontalLayout",
                    "elements": [
                        _fd_ctrl("numPixelsX", "Pixels X"),
                        _fd_ctrl("numPixelsY", "Pixels Y"),
                    ],
                },
                _fd_ctrl("spatialRegistration", "Spatial Registration"),
            ],
        },
        # Tabular data details
        {
            "type": "Group",
            "label": "Tabular Data Details",
            "rule": _hp_mime_rule(TABULAR_MIMES),
            "elements": [
                _fd_ctrl("_tabularComponentType", "Component Type"),
                {
                    "type": "HorizontalLayout",
                    "elements": [
                        _fd_ctrl("csvw:delimiter", "Delimiter"),
                        _fd_ctrl("csvw:quoteChar", "Quote Character"),
                        _fd_ctrl("csvw:commentPrefix", "Comment Prefix"),
                    ],
                },
                {
                    "type": "HorizontalLayout",
                    "elements": [
                        _fd_ctrl("csvw:header", "Has Header"),
                        _fd_ctrl("csvw:headerRowCount", "Header Row Count"),
                    ],
                },
                {
                    "type": "HorizontalLayout",
                    "elements": [
                        _fd_ctrl("countRows", "Row Count"),
                        _fd_ctrl("countColumns", "Column Count"),
                    ],
                },
                {
                    "type": "Control",
                    "scope": "#/properties/fileDetail/properties/cdi:hasPhysicalMapping",
                    "label": "Physical Mapping",
                    "options": {
                        "elementLabelProp": "cdi:formats_InstanceVariable",
                        "detail": PHYSICAL_MAPPING_DETAIL,
                    },
                },
            ],
        },
        # Data cube details
        {
            "type": "Group",
            "label": "Data Cube Details",
            "rule": _hp_mime_rule(DATACUBE_MIMES),
            "elements": [
                _fd_ctrl("_dataCubeComponentType", "Component Type"),
                {
                    "type": "Control",
                    "scope": "#/properties/fileDetail/properties/cdi:hasPhysicalMapping",
                    "label": "Physical Mapping",
                    "options": {
                        "elementLabelProp": "cdi:formats_InstanceVariable",
                        "detail": PHYSICAL_MAPPING_DATACUBE_DETAIL,
                    },
                },
                _fd_ctrl("dataComponentResource", "Data Component Resource"),
            ],
        },
        # Document details
        {
            "type": "Group",
            "label": "Document Details",
            "rule": _hp_mime_rule(DOCUMENT_MIMES),
            "elements": [
                _fd_ctrl("_documentComponentType", "Component Type"),
                _fd_ctrl("schema:version", "Version"),
                _fd_ctrl("schema:isBasedOn", "Based On"),
            ],
        },
    ],
}

# MIME types eligible for "Describe Physical Structure" toggle
PHYSICAL_STRUCTURE_MIMES = TABULAR_MIMES + SPREADSHEET_MIMES + DATACUBE_MIMES

# Detail layout for hasPart items in bundle wizard (injected via _walk).
# Includes a "Describe Physical Structure" toggle that reveals physical
# mapping controls for tabular/spreadsheet/datacube file types.
BUNDLE_HAS_PART_DETAIL = {
    "type": "VerticalLayout",
    "elements": [
        {"type": "Control", "scope": "#/properties/schema:name", "label": "File Name"},
        {
            "type": "HorizontalLayout",
            "elements": [
                {"type": "Control", "scope": "#/properties/schema:encodingFormat", "label": "MIME Type"},
                {"type": "Control", "scope": "#/properties/schema:size/properties/schema:value", "label": "Size (bytes)"},
            ],
        },
        {"type": "Control", "scope": "#/properties/schema:description", "label": "Description", "options": {"multi": True, "rows": 2, "autoGrow": True}},
        # MIME-type-gated Component Type dropdowns (filtered per file category)
        {
            "type": "Group",
            "label": "Image Details",
            "rule": _hp_mime_rule(IMAGE_MIMES),
            "elements": [_fd_ctrl("_imageComponentType", "Component Type")],
        },
        {
            "type": "Group",
            "label": "Tabular Data Details",
            "rule": _hp_mime_rule(TABULAR_MIMES),
            "elements": [_fd_ctrl("_tabularComponentType", "Component Type")],
        },
        {
            "type": "Group",
            "label": "Data Cube Details",
            "rule": _hp_mime_rule(DATACUBE_MIMES),
            "elements": [_fd_ctrl("_dataCubeComponentType", "Component Type")],
        },
        {
            "type": "Group",
            "label": "Document Details",
            "rule": _hp_mime_rule(DOCUMENT_MIMES),
            "elements": [_fd_ctrl("_documentComponentType", "Component Type")],
        },
        # Toggle — only visible for tabular/spreadsheet/datacube MIME types.
        # Uses OR with individual const conditions (enum not reliably supported
        # in CzForm rule conditions).
        {
            "type": "Control",
            "scope": "#/properties/_showPhysicalStructure",
            "label": "Describe Physical Structure",
            "rule": {
                "effect": "SHOW",
                "condition": {
                    "type": "OR",
                    "conditions": [
                        {"scope": "#/properties/schema:encodingFormat", "schema": {"const": mime}}
                        for mime in PHYSICAL_STRUCTURE_MIMES
                    ],
                },
            },
        },
        # Tabular physical mapping (CSV/TSV/spreadsheet)
        {
            "type": "Group",
            "label": "Tabular Data Structure",
            "rule": {
                "effect": "SHOW",
                "condition": {
                    "type": "AND",
                    "conditions": [
                        {"scope": "#/properties/_showPhysicalStructure", "schema": {"const": True}},
                        {
                            "type": "OR",
                            "conditions": [
                                {"scope": "#/properties/schema:encodingFormat", "schema": {"const": mime}}
                                for mime in TABULAR_MIMES + SPREADSHEET_MIMES
                            ],
                        },
                    ],
                },
            },
            "elements": [
                {
                    "type": "HorizontalLayout",
                    "elements": [
                        _fd_ctrl("csvw:delimiter", "Delimiter"),
                        _fd_ctrl("csvw:header", "Has Header"),
                        _fd_ctrl("csvw:headerRowCount", "Header Row Count"),
                    ],
                },
                {
                    "type": "HorizontalLayout",
                    "elements": [
                        _fd_ctrl("countRows", "Row Count"),
                        _fd_ctrl("countColumns", "Column Count"),
                    ],
                },
                {
                    "type": "Control",
                    "scope": "#/properties/fileDetail/properties/cdi:hasPhysicalMapping",
                    "label": "Column Mapping",
                    "options": {
                        "elementLabelProp": "cdi:formats_InstanceVariable",
                        "detail": PHYSICAL_MAPPING_DETAIL,
                        "initCollapsed": True,
                    },
                },
            ],
        },
        # Data cube physical mapping (HDF5/NetCDF)
        {
            "type": "Group",
            "label": "Data Cube Structure",
            "rule": {
                "effect": "SHOW",
                "condition": {
                    "type": "AND",
                    "conditions": [
                        {"scope": "#/properties/_showPhysicalStructure", "schema": {"const": True}},
                        {
                            "type": "OR",
                            "conditions": [
                                {"scope": "#/properties/schema:encodingFormat", "schema": {"const": mime}}
                                for mime in DATACUBE_MIMES
                            ],
                        },
                    ],
                },
            },
            "elements": [
                {
                    "type": "Control",
                    "scope": "#/properties/fileDetail/properties/cdi:hasPhysicalMapping",
                    "label": "Variable Mapping",
                    "options": {
                        "elementLabelProp": "cdi:formats_InstanceVariable",
                        "detail": PHYSICAL_MAPPING_DATACUBE_DETAIL,
                        "initCollapsed": True,
                    },
                },
            ],
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
                            "schema": {"const": "application/zip"},
                        },
                    ],
                },
            },
        },
        # --- File-type detail groups (shown based on MIME type) ---
        IMAGE_DETAIL_GROUP,
        TABULAR_DETAIL_GROUP,
        DATACUBE_DETAIL_GROUP,
        DOCUMENT_DETAIL_GROUP,
        # --- Web API fields ---
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

# Distribution detail WITHOUT ADA-specific fileDetail groups.
# Used for non-ADA profiles (e.g. CDIFDiscovery) that don't have fileDetail
# in their distribution schema.  Includes CDIF-specific fields like checksum,
# provider, terms of service, and potential action.
DISTRIBUTION_DETAIL_BASIC = {
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
        # --- Data Download fields ---
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
            "scope": "#/properties/spdx:checksum",
            "label": "Checksum",
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
                            "schema": {"const": "application/zip"},
                        },
                    ],
                },
            },
        },
        # --- Web API fields ---
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
        {
            "type": "Control",
            "scope": "#/properties/schema:potentialAction",
            "label": "Potential Action",
            "rule": {
                "effect": "SHOW",
                "condition": {
                    "scope": "#/properties/_distributionType",
                    "schema": {"const": "Web API"},
                },
            },
        },
        # --- Fields visible for all distribution types ---
        {
            "type": "Control",
            "scope": "#/properties/schema:provider",
            "label": "Provider",
        },
        {
            "type": "Control",
            "scope": "#/properties/schema:termsOfService",
            "label": "Terms of Service",
        },
    ],
}


# ---------------------------------------------------------------------------
# Schema defaults injection
# ---------------------------------------------------------------------------

def _is_ada_profile(profile_name):
    """Return True if this is an ADA profile (has fileDetail in distribution)."""
    return profile_name and profile_name.startswith("ada")


def inject_schema_defaults(schema, profile_name=None):
    """Add default values and injected properties at serve time.

    - variableMeasured items: @type default, _showAdvanced boolean
    - distribution items: _distributionType enum, WebAPI properties
    - encodingFormat: enum for MIME type selection (filtered per profile)
    - Relax restrictive @type enum constraints so frontend AJV doesn't reject
      multi-typed items (e.g. variableMeasured with both PropertyValue and
      InstanceVariable).
    """
    result = copy.deepcopy(schema)

    # --- variableMeasured defaults ---
    var_measured = (
        result.get("properties", {}).get("schema:variableMeasured", {})
    )
    items = var_measured.get("items", {})
    items_props = items.get("properties", {})

    at_type = items_props.get("@type", {})
    if isinstance(at_type, dict) and at_type.get("type") == "array":
        # Relax single-value enum on items so multi-typed values pass AJV.
        # e.g. enum: ["schema:PropertyValue"] → items: {type: string} + contains
        items_enum = at_type.get("items", {})
        if isinstance(items_enum, dict) and "enum" in items_enum:
            required_type = items_enum["enum"][0] if items_enum["enum"] else None
            at_type["items"] = {"type": "string"}
            if required_type:
                at_type["contains"] = {"const": required_type}
            at_type.setdefault("minItems", 1)

        if "default" not in at_type:
            at_type["default"] = ["schema:PropertyValue", "cdi:InstanceVariable"]

    # Inject _showAdvanced boolean for advanced toggle
    if items_props:
        items_props["_showAdvanced"] = {"type": "boolean", "default": False}

    # --- distribution defaults ---
    distribution = result.get("properties", {}).get("schema:distribution", {})
    dist_items = distribution.get("items", {})
    dist_props = dist_items.get("properties", {})

    if dist_props:
        # Relax distribution @type enum so both DataDownload and WebAPI pass AJV
        dist_at_type = dist_props.get("@type", {})
        if isinstance(dist_at_type, dict) and dist_at_type.get("type") == "array":
            dist_type_items = dist_at_type.get("items", {})
            if isinstance(dist_type_items, dict) and "enum" in dist_type_items:
                dist_at_type["items"] = {"type": "string"}
                dist_at_type.pop("contains", None)

        # Type selector field
        dist_props["_distributionType"] = {
            "type": "string",
            "enum": ["Data Download", "Web API"],
            "default": "Data Download",
        }
        # WebAPI properties (not in OGC BB schema, injected at serve time)
        dist_props.setdefault("schema:serviceType", {"type": "string"})
        dist_props.setdefault("schema:documentation", {"type": "string", "format": "uri"})

        # Remove properties not covered by the ADA distribution uischema.
        # These cause "No applicable renderer found" when CzForm tries to
        # auto-render them in the flattened distribution layout.
        if _is_ada_profile(profile_name):
            for unused_prop in ["schema:provider", "schema:termsOfService",
                                "schema:potentialAction", "resultTarget",
                                "schema:result", "schema:relatedLink"]:
                dist_props.pop(unused_prop, None)

        # Replace array encodingFormat with single string + MIME enum.
        # A distribution item describes one file with one MIME type;
        # single string enables simple {"const": "text/csv"} rule conditions.
        # The serializer wraps back to array on save.
        mime_enum = _get_profile_mime_enum(profile_name)
        dist_props["schema:encodingFormat"] = {
            "type": "string",
            "enum": mime_enum,
        }

        # Replace hasPart encodingFormat with single string + MIME enum
        # (same pattern as distribution-level encodingFormat)
        has_part = dist_props.get("schema:hasPart", {})
        hp_items = has_part.get("items", {})
        hp_props = hp_items.get("properties", {})
        if hp_props:
            hp_props["schema:encodingFormat"] = {
                "type": "string",
                "enum": mime_enum,
            }
            # Inject _showPhysicalStructure toggle for progressive disclosure
            hp_props["_showPhysicalStructure"] = {
                "type": "boolean",
                "default": False,
            }

        # --- physicalMapping item defaults ---
        # Inject _showAdvanced boolean and simplify formats_InstanceVariable
        # for each place physicalMapping appears (distribution-level fileDetail
        # and hasPart-level fileDetail).
        for props_container in [dist_props, hp_props]:
            fd_schema = props_container.get("fileDetail", {})
            fd_props = fd_schema.get("properties", {})
            pm = fd_props.get("cdi:hasPhysicalMapping", {})
            pm_items = pm.get("items", {})
            pm_props = pm_items.get("properties", {})
            if pm_props:
                # Inject _showAdvanced toggle
                pm_props["_showAdvanced"] = {"type": "boolean", "default": False}

                # Simplify cdi:formats_InstanceVariable from object to string
                # so CzForm renders a simple text input / dropdown.
                # The serializer wraps back to {"@id": "..."} on save.
                pm_props["cdi:formats_InstanceVariable"] = {
                    "type": "string",
                    "description": "Variable name or @id reference",
                }

        # --- Per-category componentType properties ---
        # Inject UI-only string properties with filtered enum lists so each
        # MIME-type detail group shows only relevant componentType values
        # instead of the full ~110-item list.
        if _is_ada_profile(profile_name):
            _CT_CATEGORIES = {
                "_imageComponentType": IMAGE_COMPONENT_TYPES + GENERIC_COMPONENT_TYPES,
                "_tabularComponentType": TABULAR_COMPONENT_TYPES + GENERIC_COMPONENT_TYPES,
                "_dataCubeComponentType": DATACUBE_COMPONENT_TYPES + GENERIC_COMPONENT_TYPES,
                "_documentComponentType": DOCUMENT_COMPONENT_TYPES + GENERIC_COMPONENT_TYPES,
            }
            for props_container in [dist_props, hp_props]:
                fd_schema = props_container.get("fileDetail", {})
                fd_props = fd_schema.get("properties", {})
                if fd_props:
                    for prop_name, enum_list in _CT_CATEGORIES.items():
                        fd_props[prop_name] = {"type": "string", "enum": enum_list}

    return result


# ---------------------------------------------------------------------------
# UISchema injection
# ---------------------------------------------------------------------------

def inject_uischema(uischema, person_names=None, profile_name=None):
    """Deep-copy uischema and inject layout configs on matching controls."""
    result = copy.deepcopy(uischema)
    _walk(result, person_names=person_names, profile_name=profile_name)
    return result


def _walk(node, person_names=None, profile_name=None):
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

    # --- Maintainer name suggestions ---
    if scope in MAINTAINER_SCOPES and person_names:
        _inject_maintainer_suggestions(node, person_names)

    # --- Variable panel progressive disclosure ---
    if scope in VARIABLE_MEASURED_SCOPES:
        options = node.setdefault("options", {})
        options["elementLabelProp"] = "schema:name"
        options["detail"] = copy.deepcopy(VARIABLE_DETAIL)

    # --- Distribution detail with type selector ---
    if scope in DISTRIBUTION_SCOPES:
        options = node.setdefault("options", {})
        options["elementLabelProp"] = "schema:name"
        if _is_ada_profile(profile_name):
            options["detail"] = copy.deepcopy(DISTRIBUTION_DETAIL)
            if profile_name in PROFILE_MEASUREMENT_CONTROLS:
                _inject_measurement_group(options["detail"], profile_name)
        else:
            options["detail"] = copy.deepcopy(DISTRIBUTION_DETAIL_BASIC)

    # --- hasPart detail with physical structure toggle ---
    if scope.endswith("schema:hasPart") and _is_ada_profile(profile_name):
        options = node.setdefault("options", {})
        options["elementLabelProp"] = "schema:name"
        options["detail"] = copy.deepcopy(BUNDLE_HAS_PART_DETAIL)
        if profile_name in PROFILE_MEASUREMENT_CONTROLS:
            _inject_measurement_group(options["detail"], profile_name)

    # Recurse into child nodes
    for child in node.get("elements", []):
        _walk(child, person_names=person_names, profile_name=profile_name)

    # Recurse into detail (used by array controls)
    detail = node.get("detail")
    if isinstance(detail, dict):
        _walk(detail, person_names=person_names, profile_name=profile_name)

    # Recurse into options.detail
    options = node.get("options")
    if isinstance(options, dict):
        options_detail = options.get("detail")
        if isinstance(options_detail, dict):
            _walk(options_detail, person_names=person_names, profile_name=profile_name)


def _inject_maintainer_suggestions(node, person_names):
    """Add person name suggestions to the maintainer's name control in its detail layout."""
    options = node.get("options", {})
    detail = options.get("detail", {})
    _inject_name_suggestion_in_elements(detail.get("elements", []), person_names)


def _inject_name_suggestion_in_elements(elements, person_names):
    """Walk elements (possibly nested in layouts) and add suggestion to the schema:name control."""
    for element in elements:
        if not isinstance(element, dict):
            continue
        if element.get("scope") == "#/properties/schema:name":
            elem_options = element.setdefault("options", {})
            elem_options["suggestion"] = person_names
            return
        # Recurse into nested layout elements (e.g., HorizontalLayout)
        _inject_name_suggestion_in_elements(element.get("elements", []), person_names)
