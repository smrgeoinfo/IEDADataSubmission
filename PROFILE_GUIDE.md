# Creating a New Metadata Profile

This guide walks through adding a new metadata profile to the IEDA Data Submission Portal. A profile defines the JSON Schema, form layout, and default values for a specific type of metadata record. Once created, the profile appears as a selectable option in the portal's metadata form interface.

There are two types of profiles:

- **ADA Profiles** extend the base `adaProduct` schema with technique-specific constraints (e.g., `adaEMPA`, `adaXRD`). They appear under "Analytical Method" in the profile selection page.
- **CDIF Profiles** compose CDIF discovery building blocks with domain-specific building blocks (e.g., `CDIFxas`). They appear under "CDIF Profiles" in the profile selection page.

Both types follow the same pipeline:

```
Building Blocks → Profile Schema → Resolve → Convert → Load → UI
```

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Step 1: Create Building Blocks](#step-1-create-building-blocks-if-needed)
4. [Step 2: Create the Profile Schema](#step-2-create-the-profile-schema)
5. [Step 3: Resolve the Schema](#step-3-resolve-the-schema)
6. [Step 4: Create JSON Forms Files](#step-4-create-json-forms-files-uischema--defaults)
7. [Step 5: Register in the Conversion Script](#step-5-register-in-the-conversion-script)
8. [Step 6: Generate the Draft 7 Schema](#step-6-generate-the-draft-7-schema)
9. [Step 7: Add Frontend Labels](#step-7-add-frontend-labels)
10. [Step 8: Load and Deploy](#step-8-load-and-deploy)
11. [Step 9: Validate](#step-9-validate)
12. [Quick Reference: ADA Technique Profile](#quick-reference-ada-technique-profile)
13. [Quick Reference: CDIF Domain Profile](#quick-reference-cdif-domain-profile)
14. [Schema Authoring Rules](#schema-authoring-rules)
15. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Python 3.10+ with `pyyaml` and `jsonschema` installed
- Docker with the portal stack running (`docker-compose-dev.yml` or `docker-compose-demo.yml`)
- The repository cloned with submodules: `git clone --recurse-submodules`

All paths below are relative to the repository root (`IEDADataSubmission/`).

---

## Architecture Overview

```
BuildingBlockSubmodule/
├── _sources/
│   ├── schemaorgProperties/     # Shared CDIF building blocks (cdifMandatory, cdifOptional, etc.)
│   ├── adaProperties/           # ADA-specific building blocks (instruments, files, details)
│   ├── xasProperties/           # XAS-specific building blocks (source, monochromator, sample)
│   ├── profiles/
│   │   ├── adaProduct/          # Base ADA profile
│   │   ├── adaEMPA/             # ADA technique profile (extends adaProduct)
│   │   ├── CDIFDiscovery/       # Base CDIF profile
│   │   └── CDIFxas/             # CDIF domain profile (composes CDIF + XAS blocks)
│   └── jsonforms/profiles/
│       ├── adaProduct/          # Hand-crafted uischema.json + defaults.json
│       ├── adaEMPA/
│       ├── CDIFDiscovery/
│       └── CDIFxas/
├── build/jsonforms/profiles/    # Generated output (schema.json + copied uischema/defaults)
└── tools/
    ├── resolve_schema.py        # Resolves $ref → single JSON file
    ├── convert_for_jsonforms.py  # Draft 2020-12 → Draft 7 for JSON Forms
    └── compare_schemas.py       # Validates YAML/JSON schema consistency
```

The pipeline for each profile:

```
schema.yaml ──resolve_schema.py──► resolvedSchema.json ──convert_for_jsonforms.py──► schema.json
                                                                                       │
uischema.json (hand-crafted) ─────────────────────────────────────────────────────────►│ build/
defaults.json (hand-crafted) ─────────────────────────────────────────────────────────►│ jsonforms/
                                                                                       │ profiles/
                                                                                       ▼ {name}/
                                                                    load_profiles.py ──► Database
                                                                                          │
                                                                                          ▼
                                                                    GET /api/catalog/profiles/{name}/
                                                                          │
                                                                          ▼
                                                                    Frontend form renders
```

---

## Step 1: Create Building Blocks (if needed)

If your profile needs domain-specific constraints not covered by existing building blocks, create new ones.

### Directory structure

Each building block is a directory under `BuildingBlockSubmodule/_sources/`. Create a domain directory (e.g., `xasProperties/`) with subdirectories for each building block:

```
_sources/xasProperties/
├── xasRequired/
│   ├── bblock.json              # Metadata about this building block
│   ├── schema.yaml              # JSON Schema source (YAML format)
│   ├── xasRequiredSchema.json   # Parallel JSON schema (keep in sync with YAML)
│   ├── context.jsonld            # JSON-LD namespace mappings (optional)
│   ├── description.md            # Human-readable description
│   └── exampleXasRequired.json   # Example instance for validation testing
├── xasOptional/
│   └── ...
└── xasSample/
    └── ...
```

### bblock.json

Required metadata file. Copy from an existing building block and adjust:

```json
{
  "$schema": "metaschema.yaml",
  "name": "XAS Required Properties",
  "abstract": "Required properties for XAS metadata: source, monochromator, sample",
  "status": "under-development",
  "dateTimeAddition": "2026-02-11T00:00:00Z",
  "itemClass": "schema",
  "register": "cdif-building-block-register",
  "version": "0.1",
  "dateOfLastChange": "2026-02-11",
  "link": "https://github.com/usgin/metadataBuildingBlocks",
  "maturity": "draft",
  "scope": "unstable",
  "tags": ["xas", "spectroscopy", "cdif"],
  "sources": [
    {"title": "XAS Data Interchange", "link": "https://github.com/XraySpectroscopy/XAS-Data-Interchange"}
  ]
}
```

### schema.yaml

The JSON Schema in YAML format. Use `$ref` to reference other building blocks and `$defs` for local definitions:

```yaml
---
$schema: https://json-schema.org/draft/2020-12/schema
allOf:
- $ref: '#/$defs/CdifMandatory'    # Reference to a local $def
- type: object
  properties:
    prov:wasGeneratedBy:
      type: array
      items:
        type: object
        properties:
          prov:used:
            type: array
            items:
              $ref: '#/$defs/AdditionalProperty'    # Reference to a local $def
$defs:
  CdifMandatory:
    $ref: ../../schemaorgProperties/cdifMandatory/cdifMandatorySchema.json   # Relative $ref to another BB
  AdditionalProperty:
    $ref: ../../schemaorgProperties/additionalProperty/additionalPropertySchema.json
```

### Parallel JSON Schema

For each `schema.yaml`, maintain a parallel `{name}Schema.json` file with the same structure in JSON format. This allows other building blocks to `$ref` the JSON file directly. **Keep both files in sync.** Run `python tools/compare_schemas.py` to detect drift.

### Example instance

Create an example JSON instance that validates against the building block schema. This is used for testing. Use realistic values where constraints exist (e.g., `const`, `enum`) and placeholder strings elsewhere.

---

## Step 2: Create the Profile Schema

Create a profile directory under `BuildingBlockSubmodule/_sources/profiles/`.

### For an ADA technique profile

Create `_sources/profiles/adaXRF/schema.yaml`:

```yaml
$schema: https://json-schema.org/draft/2020-12/schema
title: ADA XRF Product Profile
description: >-
  Technique-specific profile for X-ray Fluorescence (XRF) products.
  Extends the base ADA product profile with XRF constraints.
allOf:
  - $ref: ../adaProduct/schema.yaml        # Inherit all base ADA properties
  - type: object
    properties:
      "schema:additionalType":
        contains:
          enum:
            - "ada:XRFTabular"              # Valid component types for this technique
            - "ada:XRFCollection"
      "schema:distribution":
        items:
          properties:
            "schema:hasPart":
              items:
                properties:
                  "schema:additionalType":
                    items:
                      enum:                 # Valid file types
                        - "ada:XRFTabular"
                        - "ada:calibrationFile"
                        - "ada:supplementaryImage"
                  fileDetail:
                    anyOf:                  # Valid file detail schemas
                      - $ref: ../../adaProperties/tabularData/schema.yaml
                      - $ref: ../../adaProperties/document/schema.yaml
```

Also create `bblock.json`, `context.jsonld`, and `description.md` in the same directory.

### For a CDIF domain profile

Create `_sources/profiles/CDIFxas/schema.yaml`:

```yaml
---
$schema: https://json-schema.org/draft/2020-12/schema
type: object
title: CDIF XAS Metadata Profile
description: >-
  CDIF discovery metadata profile with XAS-specific extensions for
  X-ray absorption spectroscopy datasets.
allOf:
- $ref: ../../schemaorgProperties/cdifMandatory/cdifMandatorySchema.json
- $ref: ../../schemaorgProperties/cdifOptional/cdifOptionalSchema.json
- $ref: ../../xasProperties/xasOptional/xasOptionalSchema.json
- $ref: ../../xasProperties/xasRequired/xasRequiredSchema.json
```

The `allOf` composition merges all properties from each referenced schema.

---

## Step 3: Resolve the Schema

From the `BuildingBlockSubmodule/` directory, run:

```bash
python tools/resolve_schema.py <ProfileName> --flatten-allof \
  -o _sources/profiles/<ProfileName>/resolvedSchema.json
```

Example:

```bash
python tools/resolve_schema.py CDIFxas --flatten-allof \
  -o _sources/profiles/CDIFxas/resolvedSchema.json
```

This resolves all `$ref` references, inlines `$defs`, and optionally flattens `allOf` entries into a single merged schema. The output is a fully self-contained Draft 2020-12 JSON Schema.

**Verify** the resolved schema looks correct by checking that all expected properties appear at the top level:

```bash
python -c "
import json
s = json.load(open('_sources/profiles/CDIFxas/resolvedSchema.json'))
props = s.get('properties', {}) or s.get('allOf', [{}])[0].get('properties', {})
for k in sorted(props.keys()):
    print(k)
"
```

---

## Step 4: Create JSON Forms Files (UISchema + Defaults)

Create a directory for your profile's hand-crafted form files:

```
_sources/jsonforms/profiles/<ProfileName>/
├── uischema.json    # Form layout (tabs, groups, field order, widgets)
└── defaults.json    # Default values pre-populated in new forms
```

### uischema.json

The UISchema controls how the form is laid out. Use `Categorization` type for a tabbed interface:

```json
{
  "type": "Categorization",
  "elements": [
    {
      "type": "Category",
      "label": "Basic Info",
      "elements": [
        {
          "type": "Group",
          "label": "Basic Information",
          "elements": [
            {
              "type": "Control",
              "scope": "#/properties/schema:name",
              "label": "Dataset Name"
            },
            {
              "type": "Control",
              "scope": "#/properties/schema:description",
              "label": "Description",
              "options": { "multi": true }
            }
          ]
        }
      ]
    },
    {
      "type": "Category",
      "label": "Attribution",
      "elements": [ ... ]
    }
  ]
}
```

#### UISchema scope rules

- All schema.org properties use the `schema:` prefix in scopes: `#/properties/schema:name`, NOT `#/properties/name`
- Nested object properties: `#/properties/schema:subjectOf/properties/schema:maintainer`
- Array items detail layout: use `options.detail` on the Control
- Ordered lists: use `options.showSortButtons: true`
- Label display in collapsed arrays: use `options.elementLabelProp: "schema:name"`

#### UISchema element types

| Type | Purpose | Example |
|------|---------|---------|
| `Categorization` | Tab container (root) | Wraps Category elements |
| `Category` | Single tab | `"label": "Basic Info"` |
| `Group` | Visual grouping with header | `"label": "Creators"` |
| `Control` | Single form field | `"scope": "#/properties/schema:name"` |
| `HorizontalLayout` | Side-by-side fields | Wrap two Controls |
| `VerticalLayout` | Stacked fields | Default layout within detail |

#### Array field with detail layout

For array properties like creators, distributions, or instruments, provide a `detail` layout:

```json
{
  "type": "Control",
  "scope": "#/properties/schema:creator/properties/@list",
  "label": "Authors (ordered)",
  "options": {
    "showSortButtons": true,
    "elementLabelProp": "schema:name",
    "detail": {
      "type": "VerticalLayout",
      "elements": [
        {
          "type": "HorizontalLayout",
          "elements": [
            { "type": "Control", "scope": "#/properties/@type", "label": "Type" },
            { "type": "Control", "scope": "#/properties/schema:name", "label": "Name" }
          ]
        },
        {
          "type": "Control",
          "scope": "#/properties/schema:identifier",
          "label": "ORCID / Identifier"
        }
      ]
    }
  }
}
```

Note: scopes inside `detail` are relative to the array item, so they start with `#/properties/` (the item's properties), not the root schema.

### defaults.json

Pre-populated values for new forms. Include the `@context` with all necessary namespace prefixes and any fixed/default values:

```json
{
  "@context": {
    "schema": "http://schema.org/",
    "dcterms": "http://purl.org/dc/terms/",
    "prov": "http://www.w3.org/ns/prov#",
    "cdi": "http://ddialliance.org/Specification/DDI-CDI/1.0/RDF/"
  },
  "@type": ["schema:Dataset", "schema:Product"],
  "schema:name": "",
  "schema:creator": { "@list": [] },
  "schema:contributor": [],
  "schema:funding": [],
  "schema:license": [],
  "schema:distribution": [],
  "schema:subjectOf": {
    "@type": "schema:Dataset",
    "dcterms:conformsTo": [
      { "@id": "https://w3id.org/cdif/profiles/discovery" }
    ]
  }
}
```

For technique-specific profiles, include any values that are always the same. For example, the CDIFxas defaults pre-populate the XAS measurement technique:

```json
{
  "schema:measurementTechnique": [
    {
      "@type": "schema:DefinedTerm",
      "schema:name": "X-Ray Absorption Spectroscopy",
      "schema:termCode": "XAS",
      "schema:identifier": "http://purl.org/pan-science/PaNET/PaNET01196",
      "schema:inDefinedTermSet": "http://purl.org/pan-science/PaNET/PaNET.owl"
    }
  ]
}
```

**Tip:** Copy the defaults from the closest existing profile and modify. Use `CDIFDiscovery` as the base for CDIF profiles and `adaProduct` (or a technique profile like `adaEMPA`) as the base for ADA profiles.

---

## Step 5: Register in the Conversion Script

Edit `BuildingBlockSubmodule/tools/convert_for_jsonforms.py` and add your profile name to the appropriate list (near the top of the file):

```python
# For ADA technique profiles:
ADA_PROFILES = ["adaProduct", "adaEMPA", "adaXRD", "adaICPMS", "adaVNMIR", "adaXRF"]

# For CDIF domain profiles:
CDIF_PROFILES = ["CDIFDiscovery", "CDIFxas"]
```

### For ADA technique profiles only

If your ADA profile extends `adaProduct`, also add the parent-child relationship in `dspback-django/records/management/commands/load_profiles.py`:

```python
PARENT_PROFILES = {
    "adaEMPA": "adaProduct",
    "adaICPMS": "adaProduct",
    "adaVNMIR": "adaProduct",
    "adaXRD": "adaProduct",
    "adaXRF": "adaProduct",    # <-- Add this
}
```

This sets the `base_profile` foreign key in the database, which the frontend uses to display ADA technique profiles under the "Analytical Method" section.

CDIF profiles do **not** need a `PARENT_PROFILES` entry. They are auto-discovered by the frontend based on name pattern.

---

## Step 6: Generate the Draft 7 Schema

From the `BuildingBlockSubmodule/` directory, run:

```bash
# Single profile:
python tools/convert_for_jsonforms.py --profile <ProfileName>

# All profiles:
python tools/convert_for_jsonforms.py --all
```

This reads `_sources/profiles/<ProfileName>/resolvedSchema.json`, converts it to JSON Forms-compatible Draft 7, and writes the output to `build/jsonforms/profiles/<ProfileName>/schema.json`. It also copies `uischema.json` and `defaults.json` from `_sources/jsonforms/profiles/` to the build directory.

**Verify** the build output:

```bash
ls build/jsonforms/profiles/<ProfileName>/
# Should show: schema.json  uischema.json  defaults.json
```

---

## Step 7: Add Frontend Labels

Two files need updating so the profile displays a human-readable name and description in the UI.

### 7a. i18n strings

Edit `dspfront/src/i18n/messages.ts`. Add your profile under `metadata.ada.profiles`:

```ts
// Inside messages.en.metadata.ada.profiles:
adaXRF: {
  name: `X-Ray Fluorescence (XRF)`,
  description: `Metadata for X-ray fluorescence datasets.`,
},
```

Or for a CDIF profile:

```ts
CDIFxas: {
  name: `X-Ray Absorption Spectroscopy (XAS)`,
  description: `CDIF metadata for XAS datasets, including X-ray source, monochromator, sample, absorption edge, and target element.`,
},
```

### 7b. Form title

Edit `dspfront/src/components/metadata/geodat.ada-profile-form.vue`. Find the `profileNames` map inside the `formTitle` getter and add your profile:

```ts
const profileNames: Record<string, string> = {
  adaProduct: 'ADA Product Metadata',
  adaEMPA: 'ADA EMPA Product Metadata',
  adaXRD: 'ADA XRD Product Metadata',
  adaICPMS: 'ADA ICP-MS Product Metadata',
  adaVNMIR: 'ADA VNMIR Product Metadata',
  CDIFxas: 'CDIF XAS Metadata',
  adaXRF: 'ADA XRF Product Metadata',    // <-- Add this
}
```

### How profiles appear in the UI

The profile selection page (`geodat.ada-select-type.vue`) fetches all profiles from `/api/catalog/profiles/` and groups them into three sections:

| Section | Logic | Examples |
|---------|-------|---------|
| **General Product** | Profile named `adaProduct` | `adaProduct` |
| **Analytical Method** | Profiles with `base_profile === 'adaProduct'` | `adaEMPA`, `adaXRD`, `adaICPMS`, `adaVNMIR` |
| **CDIF Profiles** | Profile name starts with `CDIF` (excluding `CDIFDiscovery`) | `CDIFxas` |

ADA technique profiles appear automatically once the `base_profile` FK is set by `load_profiles.py`. CDIF profiles appear automatically by naming convention. No additional UI code changes are needed.

---

## Step 8: Load and Deploy

### Load the profile into the catalog database

```bash
docker exec catalog python manage.py load_profiles
```

Expected output:

```
  Updated: CDIFDiscovery
  Created: CDIFxas          ← Your new profile
  Updated: adaEMPA
  ...
Loaded 7 profiles: CDIFDiscovery, CDIFxas, adaEMPA, ...
```

### Rebuild the catalog container (if source code changed)

If you modified `load_profiles.py` (e.g., added to `PARENT_PROFILES`), rebuild:

```bash
# Dev stack:
docker compose -f docker-compose-dev.yml up -d --build catalog
docker exec catalog python manage.py load_profiles

# Demo stack:
docker compose -f docker-compose-demo.yml up -d --build catalog
docker exec catalog python manage.py load_profiles
```

### Rebuild the frontend (if i18n/Vue files changed)

For the dev stack, the frontend runs locally via Vite and picks up changes on save. For demo/production:

```bash
docker compose -f docker-compose-demo.yml up -d --build dspfront
```

### Verify the profile is accessible

```bash
# Check the profile exists in the API:
curl -s http://localhost/api/catalog/profiles/ | python -m json.tool | grep '"name"'

# Check the profile has the right schema, uischema, and defaults:
curl -s http://localhost/api/catalog/profiles/CDIFxas/ | python -m json.tool | head -20
```

---

## Step 9: Validate

### Validate the example instance against the resolved schema

```bash
cd BuildingBlockSubmodule
python -c "
import json, jsonschema
schema = json.load(open('_sources/profiles/CDIFxas/resolvedSchema.json'))
instance = json.load(open('_sources/profiles/CDIFxas/exampleCDIFxas.json'))
jsonschema.validate(instance, schema)
print('PASSED')
"
```

### Check YAML/JSON schema consistency

```bash
python tools/compare_schemas.py
```

This reports differences between `schema.yaml` and `{name}Schema.json` across all building blocks.

### Verify the form renders correctly

1. Navigate to the profile selection page (e.g., `https://localhost/metadata/ada`)
2. Your new profile should appear in the appropriate section
3. Click it to open the form
4. Verify all tabs render, required fields show asterisks, and defaults are pre-populated
5. Fill in required fields and save a test record

---

## Quick Reference: ADA Technique Profile

For a profile like `adaXRF` that extends `adaProduct`:

| Step | Action | File(s) |
|------|--------|---------|
| 1 | Create profile schema | `_sources/profiles/adaXRF/schema.yaml`, `bblock.json`, `context.jsonld`, `description.md` |
| 2 | Resolve schema | `python tools/resolve_schema.py adaXRF --flatten-allof -o _sources/profiles/adaXRF/resolvedSchema.json` |
| 3 | Create JSON Forms files | `_sources/jsonforms/profiles/adaXRF/uischema.json`, `defaults.json` |
| 4 | Register in converter | Add `"adaXRF"` to `ADA_PROFILES` in `tools/convert_for_jsonforms.py` |
| 5 | Register parent link | Add `"adaXRF": "adaProduct"` to `PARENT_PROFILES` in `load_profiles.py` |
| 6 | Generate schema | `python tools/convert_for_jsonforms.py --profile adaXRF` |
| 7 | Add form title | Add to `profileNames` in `geodat.ada-profile-form.vue` |
| 8 | Add i18n strings | Add to `metadata.ada.profiles` in `messages.ts` |
| 9 | Load profile | `docker exec catalog python manage.py load_profiles` |

---

## Quick Reference: CDIF Domain Profile

For a profile like `CDIFxas` that composes CDIF + domain blocks:

| Step | Action | File(s) |
|------|--------|---------|
| 1 | Create building blocks (if needed) | `_sources/xasProperties/xasRequired/`, etc. |
| 2 | Create profile schema | `_sources/profiles/CDIFxas/schema.yaml` |
| 3 | Resolve schema | `python tools/resolve_schema.py CDIFxas --flatten-allof -o _sources/profiles/CDIFxas/resolvedSchema.json` |
| 4 | Create JSON Forms files | `_sources/jsonforms/profiles/CDIFxas/uischema.json`, `defaults.json` |
| 5 | Register in converter | Add `"CDIFxas"` to `CDIF_PROFILES` in `tools/convert_for_jsonforms.py` |
| 6 | Generate schema | `python tools/convert_for_jsonforms.py --profile CDIFxas` |
| 7 | Add form title | Add to `profileNames` in `geodat.ada-profile-form.vue` |
| 8 | Add i18n strings | Add to `metadata.ada.profiles` in `messages.ts` |
| 9 | Load profile | `docker exec catalog python manage.py load_profiles` |

CDIF profiles are auto-discovered by name pattern (`CDIF*`, excluding `CDIFDiscovery`), so no `PARENT_PROFILES` entry is needed.

---

## Schema Authoring Rules

These are common patterns and pitfalls when writing building block schemas.

### `@type` must use array/contains pattern

```yaml
# Correct: extensible — allows adding more types
'@type':
  type: array
  items:
    type: string
  minItems: 1
  contains:
    const: schema:Dataset

# Wrong: rigid — only allows exactly this value
'@type':
  const: schema:Dataset
```

### `schema:propertyID` in contains constraints must use array/contains

The base `AdditionalProperty` schema defines `schema:propertyID` as `type: array`. When writing `contains` constraints that check for a specific property ID, the check must also expect an array:

```yaml
# Correct:
schema:propertyID:
  type: array
  contains:
    const: nxs:Field/NXsource/type

# Wrong (conflicts with base schema):
schema:propertyID:
  const: nxs:Field/NXsource/type
```

### `prov:wasGeneratedBy` must be type array

The `cdifOptional` building block defines `prov:wasGeneratedBy` as `type: array`. Any building block that is composed with `cdifOptional` (via `allOf`) must also define it as `type: array`:

```yaml
prov:wasGeneratedBy:
  type: array         # NOT type: object
  items:
    type: object
    properties:
      prov:used:
        type: array
        ...
```

### `$ref` paths in schema.yaml must point to JSON files

When referencing another building block, use relative `$ref` paths to the `.json` schema file:

```yaml
$ref: ../../schemaorgProperties/cdifMandatory/cdifMandatorySchema.json
```

### UISchema scopes must include namespace prefix

```json
// Correct:
"scope": "#/properties/schema:name"

// Wrong (will show "No applicable renderer found"):
"scope": "#/properties/name"
```

---

## Troubleshooting

### "No applicable renderer found" in the form

- Check that UISchema scopes include the `schema:` prefix
- Verify the property exists in the generated `schema.json` at the expected path
- For object properties, provide a `detail` layout in the UISchema

### Profile doesn't appear in the selection page

- For ADA profiles: verify `PARENT_PROFILES` in `load_profiles.py` maps your profile to `adaProduct`
- For CDIF profiles: verify the profile name starts with `CDIF` (case-sensitive)
- Run `docker exec catalog python manage.py load_profiles` and check the output
- Check the API: `curl http://localhost/api/catalog/profiles/`

### Schema validation errors on save

- Check the browser console for the specific validation error
- Compare your instance against the resolved schema using `jsonschema.validate()`
- Common issues: missing required properties, wrong types (string vs array), missing `@type` contains value

### resolve_schema.py fails

- Check that all `$ref` paths are valid relative paths from the schema.yaml file
- Verify referenced JSON files exist and are valid JSON
- Run with `--verbose` for detailed output

### convert_for_jsonforms.py fails

- Verify `resolvedSchema.json` exists for the profile
- Check that the profile is listed in `ADA_PROFILES` or `CDIF_PROFILES`
- Run with `--verbose` for detailed output

### Form renders but fields are missing

- Compare the UISchema scopes against the properties in `build/jsonforms/profiles/<name>/schema.json`
- Properties that exist in the schema but not the UISchema won't render in Categorization mode
- For array properties, check that the `detail` layout references the correct sub-properties
