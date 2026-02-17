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
    "ada:L2MSOverviewImage",
    "ada:NanoIRMap", "ada:SEMEBSDGrainImageMap", "ada:SEMHRCLMap",
    "ada:SEMImageMap", "ada:NanoSIMSMap", "ada:XANESimage", "ada:VNMIROverviewImage",
    "ada:EMPAQEATabular", "ada:EMPAImageCollection",
    # collection / multi-image types
    "ada:EMPAImageMap", "ada:XRDIndexedImage", "ada:VNMIRSpectraPlot",
    "ada:NanoSIMSImageCollection", "ada:XCTImageCollection",
    "ada:AIVAImageCollection", "ada:UVFMImageCollection", "ada:VLMImageCollection",
    "ada:SEMEDSElementalMaps", "ada:NanoIRMapCollection",
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
    # collection / multi-record tabular types
    "ada:NanoIRPointCollection", "ada:NanoSIMSCollection",
    "ada:LIT2DDataCollection", "ada:LITPolarDataCollection",
    "ada:MCICPMSCollection", "ada:SEMEDSPointDataCollection",
    "ada:SIMSCollection", "ada:ARGTCollection",
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
    # additional datacube types
    "ada:GCGCMSCollection", "ada:LCMSMSCollection",
    "ada:TOFSIMSCollection", "ada:XANESCollection",
    "ada:QRISCalibratedCollection", "ada:QRISRawCollection",
    "ada:RITOFNGMSCollection",
]

# document building block — shown when DOCUMENT_MIMES selected
# Supplement types (calibrationFile, contextVideo, logFile, etc.) moved to
# GENERIC_COMPONENT_TYPES so they appear in every category dropdown.
DOCUMENT_COMPONENT_TYPES = [
    "ada:ARGTDocument",
    "ada:peaks",
    "ada:QRISCalibrationFile",
    # additional document types
    "ada:SLSShapeModel", "ada:SLSPartialScan", "ada:MCICPMSRaw",
]

# Generic types available in every category dropdown.
# Includes all 22 supplement types from the Components worksheet of
# ADA-AnalyticalMethodsAndAttributes.xlsx, plus legacy building-block types
# (annotatedProduct, visImage) for backward compatibility.
GENERIC_COMPONENT_TYPES = [
    "ada:analysisLocation", "ada:annotatedImage", "ada:areaOfInterest",
    "ada:basemap", "ada:calibrationFile", "ada:code",
    "ada:contextPhotography", "ada:contextVideo", "ada:inputFile",
    "ada:instrumentMetadata", "ada:logFile", "ada:methodDescription",
    "ada:other", "ada:plot", "ada:processingMethod", "ada:quickLook",
    "ada:report", "ada:samplePreparation", "ada:shapefile",
    "ada:supplementalBasemap", "ada:supplementaryImage", "ada:worldFile",
    # Legacy types from building block schemas (not in supplement list)
    "ada:annotatedProduct", "ada:visImage",
]

# ---------------------------------------------------------------------------
# Per-profile component type mapping
#
# Maps each technique profile → its allowed ada: component types (excluding
# GENERIC_COMPONENT_TYPES which are always appended).  MIME filtering and
# componentType dropdown filtering are both derived from this dict.
# ---------------------------------------------------------------------------

PROFILE_COMPONENT_TYPES = {
    # --- Original 4 profiles (from schema.yaml hasPart enum) ---
    "adaEMPA": [
        "ada:EMPAImageMap", "ada:EMPAImage",
        "ada:EMPAQEATabular", "ada:EMPAImageCollection",
    ],
    "adaXRD": [
        "ada:XRDTabular", "ada:XRDDiffractionPattern", "ada:XRDIndexedImage",
    ],
    "adaICPMS": [
        "ada:HRICPMSProcessed", "ada:HRICPMSRaw",
        "ada:QICPMSProcessedTabular", "ada:QICPMSRawTabular",
        "ada:MCICPMSTabular", "ada:MCICPMSCollection", "ada:MCICPMSRaw",
    ],
    "adaVNMIR": [
        "ada:VNMIRSpectralPoint", "ada:VNMIROverviewImage",
        "ada:VNMIRSpectralMap", "ada:VNMIRSpectraPlot",
    ],
    # --- 31 generated profiles (from generate_profiles.py PROFILES) ---
    "adaARGT": ["ada:ARGTDocument", "ada:ARGTCollection"],
    "adaDSC": ["ada:DSCHeatTabular", "ada:DSCResultsTabular"],
    "adaEAIRMS": ["ada:EAIRMSCollection"],
    "adaICPOES": [
        "ada:ICPOESIntermediateTabular", "ada:ICPOESProcessedTabular",
        "ada:ICPOESRawTabular",
    ],
    "adaL2MS": ["ada:L2MSCube", "ada:L2MSOverviewImage"],
    "adaLAF": ["ada:LAFProcessed", "ada:LAFRaw"],
    "adaNanoIR": [
        "ada:NanoIRBackground", "ada:NanoIRMap",
        "ada:NanoIRMapCollection", "ada:NanoIRPointCollection",
    ],
    "adaNanoSIMS": [
        "ada:NanoSIMSCollection", "ada:NanoSIMSImageCollection",
        "ada:NanoSIMSTabular", "ada:NanoSIMSMap", "ada:NanoSIMSImage",
    ],
    "adaPSFD": ["ada:PSFDTabular"],
    "adaQRIS": [
        "ada:QRISCalibratedCollection", "ada:QRISRawCollection",
        "ada:QRISCalibrationFile",
    ],
    "adaSLS": ["ada:SLSShapeModel", "ada:SLSPartialScan", "ada:ShapeModelImage"],
    "adaXCT": ["ada:XCTImageCollection"],
    "adaAIVA": ["ada:AIVAImage", "ada:AIVAImageCollection"],
    "adaAMS": ["ada:AMSRawData", "ada:AMSProcessedData"],
    "adaFTICRMS": ["ada:FTICRMSTabular", "ada:FTICRMSCube"],
    "adaGCMS": ["ada:GCMSCollection", "ada:GCMSCube", "ada:GCGCMSCollection"],
    "adaGPYC": ["ada:GPYCProcessedTabular", "ada:GPYCRawTabular"],
    "adaIC": ["ada:ICTabular"],
    "adaLCMS": ["ada:LCMSCollection", "ada:LCMSMSCollection"],
    "adaLIT": ["ada:LITImage", "ada:LIT2DDataCollection", "ada:LITPolarDataCollection"],
    "adaNGNSMS": ["ada:NGNSMSRaw", "ada:NGNSMSProcessed"],
    "adaRAMAN": ["ada:RAMANRawTabular"],
    "adaRITOFNGMS": ["ada:RITOFNGMSTabular", "ada:RITOFNGMSCollection"],
    "adaSEM": [
        "ada:SEMImageCollection", "ada:SEMImageMap",
        "ada:SEMEBSDGrainImage", "ada:SEMEBSDGrainImageMap",
        "ada:SEMEBSDGrainImageMapCube",
        "ada:SEMEDSElementalMap", "ada:SEMEDSElementalMaps",
        "ada:SEMEDSElementalMapsCube",
        "ada:SEMEDSPointData", "ada:SEMEDSPointDataCollection",
        "ada:SEMEDSPointDataCube",
        "ada:SEMHRCLImage", "ada:SEMHRCLMap", "ada:SEMHRCLCube",
    ],
    "adaSIMS": ["ada:SIMSTabular", "ada:SIMSCollection"],
    "adaSVRUEC": ["ada:SVRUECTabular"],
    "adaTEM": [
        "ada:TEMImage", "ada:TEMPatternsImage", "ada:TEMEDSImageCollection",
        "ada:STEMImage", "ada:STEMEDSTabular", "ada:STEMEDSCube",
        "ada:STEMEDSTomo", "ada:STEMEELSTabular", "ada:STEMEELSCube",
    ],
    "adaToFSIMS": ["ada:TOFSIMSCollection"],
    "adaUVFM": ["ada:UVFMImage", "ada:UVFMImageCollection"],
    "adaVLM": ["ada:VLMImage", "ada:VLMImageCollection"],
    "adaXANES": [
        "ada:XANESImageStack", "ada:XANESStackOverviewImage",
        "ada:XANESRawTabular", "ada:XANESProcessedTabular",
        "ada:XANESimage", "ada:XANESCollection",
    ],
}

# ---------------------------------------------------------------------------
# Per-profile measurement detail controls
# ---------------------------------------------------------------------------

def _ct_ctrl(prop, label):
    """Shorthand for a componentType property control."""
    return {
        "type": "Control",
        "scope": f"#/properties/componentType/properties/{prop}",
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
            if "ComponentType" in scope and scope.startswith("#/properties/_"):
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

def _get_profile_category_components(profile_name, global_category_list):
    """Return componentType enum filtered by profile for a MIME category.

    Intersects the global category list with the profile's allowed types.
    Always appends GENERIC_COMPONENT_TYPES.
    Returns full category + generics for adaProduct/unknown profiles.
    """
    profile_types = PROFILE_COMPONENT_TYPES.get(profile_name)
    if profile_types is None:
        # adaProduct or unknown -> no filtering
        return global_category_list + GENERIC_COMPONENT_TYPES

    profile_set = set(profile_types)
    filtered = [t for t in global_category_list if t in profile_set]
    return filtered + GENERIC_COMPONENT_TYPES


def _derive_profile_mime_categories(profile_name):
    """Derive supported MIME categories from the profile's component types.

    Returns a set of FILE_TYPE_TO_MIMES keys, or None for no filtering.
    """
    profile_types = PROFILE_COMPONENT_TYPES.get(profile_name)
    if profile_types is None:
        return None  # No filtering (adaProduct / unknown)

    profile_set = set(profile_types)
    categories = set()

    if profile_set & set(IMAGE_COMPONENT_TYPES):
        categories.update(["image", "imageMap", "supDocImage"])
    if profile_set & set(TABULAR_COMPONENT_TYPES):
        categories.add("tabularData")
    if profile_set & set(DATACUBE_COMPONENT_TYPES):
        categories.add("dataCube")

    # Always include document and collection for all technique profiles
    categories.add("document")
    categories.add("collection")

    return categories


def _get_profile_mime_enum(profile_name):
    """Return filtered MIME enum for a profile, derived from PROFILE_COMPONENT_TYPES.

    adaProduct and unknown/unset profiles get the complete MIME list.
    Technique profiles get a filtered list based on which MIME categories
    their component types fall into, plus structured data formats always included.
    """
    if not profile_name or profile_name == "adaProduct":
        return MIME_TYPE_ENUM

    categories = _derive_profile_mime_categories(profile_name)
    if categories is None:
        return MIME_TYPE_ENUM

    allowed = set()
    for cat in categories:
        allowed.update(FILE_TYPE_TO_MIMES.get(cat, []))
    # Always include structured data formats (JSON, XML, YAML)
    allowed.update(STRUCTURED_DATA_MIMES)

    return [m for m in MIME_TYPE_ENUM if m in allowed]


# ---------------------------------------------------------------------------
# Per-profile distribution-level MIME filtering
# ---------------------------------------------------------------------------

# Maps profile → MIME categories allowed at the *distribution* level (archive + primary data).
# Profiles absent from this dict use the full hasPart-level MIME list.
# "collection" (zip) and STRUCTURED_DATA_MIMES are always added.
PROFILE_DIST_MIME_CATEGORIES = {
    "adaL2MS": {"dataCube"},
}


def _get_dist_mime_enum(profile_name):
    """Return MIME enum for the distribution level (archive + primary data).

    Profiles in PROFILE_DIST_MIME_CATEGORIES get a restricted list;
    others fall back to _get_profile_mime_enum().
    """
    cats = PROFILE_DIST_MIME_CATEGORIES.get(profile_name)
    if cats is None:
        return _get_profile_mime_enum(profile_name)

    allowed = set()
    for cat in cats:
        allowed.update(FILE_TYPE_TO_MIMES.get(cat, []))
    allowed.update(ARCHIVE_MIMES)
    allowed.update(STRUCTURED_DATA_MIMES)
    return [m for m in MIME_TYPE_ENUM if m in allowed]


def _mime_and_download_rule(mime_list):
    """Build a SHOW rule: encodingFormat in mime_list (distribution level).

    Uses flat OR with individual const conditions — the same pattern as
    _hp_mime_rule.  CzForm cannot evaluate any nesting of compound
    conditions (AND>OR, OR>AND), so the _distributionType guard is omitted.
    This is safe because the MIME dropdown defaults to application/zip
    (which doesn't match any detail group) and is hidden in Web API mode.
    """
    return {
        "effect": "SHOW",
        "condition": {
            "type": "OR",
            "conditions": [
                {"scope": "#/properties/schema:encodingFormat",
                 "schema": {"const": m}}
                for m in mime_list
            ],
        },
    }


# ---------------------------------------------------------------------------
# Distribution-level (flattened) file detail groups
#
# When the stored uischema pre-flattens distribution into separate groups
# (Archive + Files), there is no DISTRIBUTION_DETAIL injection.  These
# groups are injected directly into the Distribution category so that
# selecting a non-zip MIME at the distribution level reveals the
# appropriate file-type details.
# ---------------------------------------------------------------------------

_DIST_ENC_SCOPE = (
    "#/properties/schema:distribution/properties/schema:encodingFormat"
)
_DIST_PROP_PREFIX = "#/properties/schema:distribution/properties/"


def _dist_mime_rule(mime_list):
    """SHOW rule for distribution-level file detail groups (full scope path)."""
    return {
        "effect": "SHOW",
        "condition": {
            "type": "OR",
            "conditions": [
                {"scope": _DIST_ENC_SCOPE, "schema": {"const": m}}
                for m in mime_list
            ],
        },
    }


def _dist_ctrl(prop, label):
    """Control scoped to a distribution-level property."""
    return {
        "type": "Control",
        "scope": f"{_DIST_PROP_PREFIX}{prop}",
        "label": label,
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
    """Shorthand for a file detail property control."""
    return {
        "type": "Control",
        "scope": f"#/properties/{prop}",
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


# ---------------------------------------------------------------------------
# Distribution-level (flattened) file detail groups
#
# When the stored uischema pre-flattens distribution into separate groups
# (Archive + Files), there is no DISTRIBUTION_DETAIL injection.  These
# groups are injected directly into the Distribution category so that
# selecting a non-zip MIME at the distribution level reveals the
# appropriate file-type details.
# ---------------------------------------------------------------------------

DIST_IMAGE_DETAIL_GROUP = {
    "type": "Group",
    "label": "Image Details",
    "rule": _dist_mime_rule(IMAGE_MIMES),
    "elements": [
        _dist_ctrl("_imageComponentType", "Component Type"),
        _dist_ctrl("acquisitionTime", "Acquisition Time"),
        {
            "type": "HorizontalLayout",
            "elements": [
                _dist_ctrl("channel1", "Channel 1"),
                _dist_ctrl("channel2", "Channel 2"),
                _dist_ctrl("channel3", "Channel 3"),
            ],
        },
        _dist_ctrl("pixelSize", "Pixel Size"),
        _dist_ctrl("illuminationType", "Illumination Type"),
        _dist_ctrl("imageType", "Image Type"),
        {
            "type": "HorizontalLayout",
            "elements": [
                _dist_ctrl("numPixelsX", "Pixels X"),
                _dist_ctrl("numPixelsY", "Pixels Y"),
            ],
        },
        _dist_ctrl("spatialRegistration", "Spatial Registration"),
    ],
}

DIST_TABULAR_DETAIL_GROUP = {
    "type": "Group",
    "label": "Tabular Data Details",
    "rule": _dist_mime_rule(TABULAR_MIMES),
    "elements": [
        _dist_ctrl("_tabularComponentType", "Component Type"),
        {
            "type": "HorizontalLayout",
            "elements": [
                _dist_ctrl("csvw:delimiter", "Delimiter"),
                _dist_ctrl("csvw:quoteChar", "Quote Character"),
                _dist_ctrl("csvw:commentPrefix", "Comment Prefix"),
            ],
        },
        {
            "type": "HorizontalLayout",
            "elements": [
                _dist_ctrl("csvw:header", "Has Header"),
                _dist_ctrl("csvw:headerRowCount", "Header Row Count"),
            ],
        },
        {
            "type": "HorizontalLayout",
            "elements": [
                _dist_ctrl("countRows", "Row Count"),
                _dist_ctrl("countColumns", "Column Count"),
            ],
        },
        {
            "type": "Control",
            "scope": f"{_DIST_PROP_PREFIX}cdi:hasPhysicalMapping",
            "label": "Physical Mapping",
            "options": {
                "elementLabelProp": "cdi:formats_InstanceVariable",
                "detail": PHYSICAL_MAPPING_DETAIL,
            },
        },
    ],
}

DIST_DATACUBE_DETAIL_GROUP = {
    "type": "Group",
    "label": "Data Cube Details",
    "rule": _dist_mime_rule(DATACUBE_MIMES),
    "elements": [
        _dist_ctrl("_dataCubeComponentType", "Component Type"),
        {
            "type": "Control",
            "scope": f"{_DIST_PROP_PREFIX}cdi:hasPhysicalMapping",
            "label": "Physical Mapping",
            "options": {
                "elementLabelProp": "cdi:formats_InstanceVariable",
                "detail": PHYSICAL_MAPPING_DATACUBE_DETAIL,
            },
        },
        _dist_ctrl("dataComponentResource", "Data Component Resource"),
    ],
}

DIST_DOCUMENT_DETAIL_GROUP = {
    "type": "Group",
    "label": "Document Details",
    "rule": _dist_mime_rule(DOCUMENT_MIMES),
    "elements": [
        _dist_ctrl("_documentComponentType", "Component Type"),
        _dist_ctrl("schema:version", "Version"),
        _dist_ctrl("schema:isBasedOn", "Based On"),
    ],
}

DIST_FILE_DETAIL_GROUPS = [
    DIST_IMAGE_DETAIL_GROUP,
    DIST_TABULAR_DETAIL_GROUP,
    DIST_DATACUBE_DETAIL_GROUP,
    DIST_DOCUMENT_DETAIL_GROUP,
]

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
            "scope": "#/properties/cdi:hasPhysicalMapping",
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
            "scope": "#/properties/cdi:hasPhysicalMapping",
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
                    "scope": "#/properties/cdi:hasPhysicalMapping",
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
                    "scope": "#/properties/cdi:hasPhysicalMapping",
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
                    "scope": "#/properties/cdi:hasPhysicalMapping",
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
                    "scope": "#/properties/cdi:hasPhysicalMapping",
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

# Distribution detail WITHOUT ADA-specific file detail groups.
# Used for non-ADA profiles (e.g. CDIFDiscovery) that don't have file-type
# detail properties in their distribution schema.  Includes CDIF-specific
# fields like checksum, provider, terms of service, and potential action.
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
    """Return True if this is an ADA profile (has file detail properties in distribution)."""
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

        # Distribution level — restricted MIME list (archive + primary data)
        dist_mime_enum = _get_dist_mime_enum(profile_name)
        dist_props["schema:encodingFormat"] = {
            "type": "string",
            "enum": dist_mime_enum,
            "default": "application/zip",
        }

        # hasPart level — full MIME list (all file types within the archive)
        hp_mime_enum = _get_profile_mime_enum(profile_name)
        has_part = dist_props.get("schema:hasPart", {})
        hp_items = has_part.get("items", {})
        hp_props = hp_items.get("properties", {})
        if hp_props:
            hp_props["schema:encodingFormat"] = {
                "type": "string",
                "enum": hp_mime_enum,
            }
            # Inject _showPhysicalStructure toggle for progressive disclosure
            hp_props["_showPhysicalStructure"] = {
                "type": "boolean",
                "default": False,
            }

        # --- physicalMapping item defaults ---
        # Inject _showAdvanced boolean and simplify formats_InstanceVariable
        # for each place physicalMapping appears (distribution-level and
        # hasPart-level).
        for props_container in [dist_props, hp_props]:
            pm = props_container.get("cdi:hasPhysicalMapping", {})
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
                "_imageComponentType": _get_profile_category_components(
                    profile_name, IMAGE_COMPONENT_TYPES),
                "_tabularComponentType": _get_profile_category_components(
                    profile_name, TABULAR_COMPONENT_TYPES),
                "_dataCubeComponentType": _get_profile_category_components(
                    profile_name, DATACUBE_COMPONENT_TYPES),
                "_documentComponentType": _get_profile_category_components(
                    profile_name, DOCUMENT_COMPONENT_TYPES),
            }
            for props_container in [dist_props, hp_props]:
                if props_container:
                    for prop_name, enum_list in _CT_CATEGORIES.items():
                        props_container[prop_name] = {"type": "string", "enum": enum_list}

        # --- Copy file-detail properties to distribution level ---
        # The flattened uischema injects distribution-level file detail groups
        # (DIST_*_DETAIL_GROUP) whose controls reference properties that only
        # exist on hasPart items (from files/schema.yaml building block).
        # Copy them to dist_props so CzForm can render them.
        if hp_props:
            _FILE_DETAIL_PROPS = [
                # Data cube
                "cdi:hasPhysicalMapping", "dataComponentResource",
                # Image
                "acquisitionTime", "channel1", "channel2", "channel3",
                "pixelSize", "illuminationType", "imageType",
                "numPixelsX", "numPixelsY", "spatialRegistration",
                # Tabular
                "csvw:delimiter", "csvw:quoteChar", "csvw:commentPrefix",
                "csvw:header", "csvw:headerRowCount",
                "countRows", "countColumns",
                # Document
                "schema:version", "schema:isBasedOn",
                # componentType (source object for measurement details)
                "componentType",
            ]
            for prop in _FILE_DETAIL_PROPS:
                if prop in hp_props and prop not in dist_props:
                    dist_props[prop] = copy.deepcopy(hp_props[prop])

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

    # --- Distribution-level file detail groups (flattened uischema) ---
    # When the stored uischema pre-flattens distribution into separate
    # groups (Archive + Files), inject file-type detail groups and a
    # zip-only rule on the hasPart group so that selecting a non-zip
    # MIME at the distribution level shows the right detail controls.
    if (node.get("type") == "Category"
            and node.get("label") == "Distribution"
            and _is_ada_profile(profile_name)):
        _inject_dist_file_detail_groups(node, profile_name)

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


def _inject_dist_file_detail_groups(dist_category, profile_name):
    """Inject distribution-level file-type detail groups into a flattened Distribution category.

    When the stored uischema pre-flattens distribution (Archive group + Files group),
    there are no file-type detail groups at the distribution level.  This function:
    1. Adds a SHOW rule on the hasPart group/control so it only shows for zip
    2. Appends file-type detail groups (Image, Tabular, Data Cube, Document)
       to the Distribution category so non-zip MIMEs reveal their details.
    """
    elements = dist_category.get("elements", [])
    if not elements:
        return

    # Check that this is a flattened uischema (has distribution-scoped controls,
    # not a plain #/properties/schema:distribution array control).
    has_flattened_dist = any(
        _DIST_PROP_PREFIX in str(el)
        for el in elements
    )
    if not has_flattened_dist:
        return

    # Add zip-only SHOW rule on the group containing hasPart
    for el in elements:
        if _has_scope_ending(el, "schema:hasPart"):
            el.setdefault("rule", {
                "effect": "SHOW",
                "condition": {
                    "scope": _DIST_ENC_SCOPE,
                    "schema": {"const": "application/zip"},
                },
            })
            break

    # Append distribution-level file-type detail groups
    for group in DIST_FILE_DETAIL_GROUPS:
        injected = copy.deepcopy(group)
        if profile_name in PROFILE_MEASUREMENT_CONTROLS:
            _inject_measurement_group(injected, profile_name)
        elements.append(injected)


def _has_scope_ending(node, suffix):
    """Check if node or any descendant has a scope ending with suffix."""
    if not isinstance(node, dict):
        return False
    if node.get("scope", "").endswith(suffix):
        return True
    return any(_has_scope_ending(el, suffix) for el in node.get("elements", []))
