# IEDA Data Submission Portal

A web application for submitting, managing, and discovering research data across multiple Earth Science repositories. This monorepo contains the backend API, frontend application, deployment configuration, and OGC Building Blocks for schema modularization.

`dspback` and `dspfront` are included as [git submodules](https://git-scm.com/book/en/v2/Git-Tools-Submodules) pointing to their respective repositories on the `develop` branch.

## Repository Structure

```
IEDADataSubmission/
├── dspback/                 # FastAPI backend (submodule → smrgeoinfo/dspback)
├── dspfront/                # Vue.js frontend (submodule → smrgeoinfo/dspfront)
├── OCGbuildingBlockTest/    # OGC Building Block schemas (YAML/JSON-LD)
├── scrapers/                # Repository metadata scrapers
├── jsonld/                  # JSON-LD normalization examples
├── nginx/                   # Nginx reverse proxy configs
├── docker-compose-dev.yml   # Development stack (backend + nginx)
├── docker-compose-upstream.yml  # Full stack from source
├── docker-compose-artifact-registry.yml  # Full stack from registry
└── .env                     # Environment variables
```

## Components

### dspback — Backend API

FastAPI application providing a standardized metadata API across multiple repository types.

- **Framework:** FastAPI with async MongoDB (Motor/Beanie)
- **Authentication:** ORCID OAuth2 for users, per-repository OAuth2 for repository access
- **Schema-driven forms:** Each repository has a JSON Schema, UI Schema, and defaults file that drive dynamic form generation on the frontend

#### Supported Repositories

| Repository | Type | OAuth | Description |
|---|---|---|---|
| HydroShare | Form + Registration | Yes | Hydrologic data and models |
| EarthChem | Form + Registration | Yes | Geochemical and petrological data |
| Zenodo | Registration only | Yes | General-purpose research data |
| External | Form only | No | Generic dataset registration for any repository |
| **ADA** | **Form + JSON-LD ingest** | **No** | **Astromat Data Archive — analytical data from astromaterials research** |

#### Key Backend Files

```
dspback/dspback/
├── api.py                  # FastAPI app setup, router registration, middleware
├── pydantic_schemas.py     # RepositoryType enum, record models (Zenodo, HydroShare, EarthChem, External, ADA)
├── config/__init__.py      # Settings, OAuth config, repository_config dict
├── routers/
│   ├── ada.py              # ADA CRUD endpoints
│   ├── external.py         # External dataset CRUD endpoints
│   ├── hydroshare.py       # HydroShare integration
│   ├── zenodo.py           # Zenodo integration
│   ├── earthchem.py        # EarthChem integration
│   ├── submissions.py      # Cross-repository submission management
│   ├── metadata_class.py   # Base class for metadata routers
│   ├── authentication.py   # ORCID login flow
│   └── discovery.py        # Search and discovery API
├── schemas/
│   ├── ada/                # ADA JSON Schema, UI Schema, defaults, generated model, JSON-LD translator
│   ├── external/           # External dataset schemas
│   ├── zenodo/             # Zenodo schemas
│   ├── hydroshare/         # HydroShare schemas
│   ├── earthchem/          # EarthChem schemas
│   └── discovery.py        # Discovery/search Pydantic models
└── dependencies.py         # Auth utilities, token management
```

#### Adding a New Repository Type

1. Add enum value to `RepositoryType` in `pydantic_schemas.py`
2. Create a `XxxRecord(BaseRecord)` Pydantic model with `to_submission()` method
3. Create `schemas/xxx/` with `schema.json`, `uischema.json`, `defaults.json`
4. Run `datamodel-codegen` to generate `model.py` from `schema.json`
5. Create `routers/xxx.py` following the `external.py` pattern
6. Register the router in `api.py`
7. Add to `repository_config` in `config/__init__.py`
8. Add to `record_type_by_repo_type` in `routers/submissions.py`

#### ADA JSON-LD Translation Endpoint

ADA has a dedicated endpoint `POST /api/metadata/ada/jsonld` that accepts raw JSON-LD from external ADA metadata tools (e.g. `ada_metadata_forms`). The JSON-LD uses namespace-prefixed keys (`schema:name`, `prov:wasGeneratedBy`, etc.) following the OGC Building Block schema (`profiles/adaProduct/schema.yaml`). The translator (`schemas/ada/translator.py`) converts this to the flat property-name format expected by CZ Net's `schema.json`.

Key mappings:
- `schema:name` → `name`, `schema:creator.@list[]` → `creators[]`
- `prov:wasGeneratedBy.prov:used[]` → `instruments[]`
- `prov:wasGeneratedBy.schema:location` → `laboratory`
- `prov:wasGeneratedBy.schema:mainEntity[]` → `samples[]`
- `schema:creativeWorkStatus` → `status`
- `cdi:unitOfMeasureKind` → `unitText`

The existing `POST /api/metadata/ada` endpoint (flat JSON) remains unchanged for the CZ Net frontend forms.

### dspfront — Frontend Application

Vue.js single-page application for browsing repositories, filling metadata forms, and managing submissions.

- **Framework:** Vue 3 with TypeScript, Vuex ORM for state management
- **Form rendering:** JSON Forms (driven by backend JSON Schema + UI Schema)
- **UI Library:** Vuetify

#### Key Frontend Files

```
dspfront/src/
├── components/
│   ├── submissions/types.ts   # EnumRepositoryKeys, IRepository, ISubmission interfaces
│   └── submit/constants.ts    # repoMetadata — name, logo, description, URLs per repo
├── models/
│   ├── repository.model.ts    # Base Vuex ORM model (init, authorize, CRUD, file ops)
│   ├── ada.model.ts           # ADA repository model
│   ├── external.model.ts      # External repository model
│   ├── hydroshare.model.ts    # HydroShare model (with file/folder ops)
│   ├── earthchem.model.ts     # EarthChem model
│   ├── zenodo.model.ts        # Zenodo model
│   ├── submission.model.ts    # Submission state model
│   └── user.model.ts          # User/auth state model
└── constants.ts               # App-wide constants
```

### Deployment & Infrastructure

Docker Compose configuration and supporting services live at the repository root.

- `docker-compose-dev.yml` — Development stack (backend + nginx with SSL)
- `docker-compose-upstream.yml` — Full stack built from source (frontend + backend)
- `docker-compose-artifact-registry.yml` — Full stack from pre-built images
- `nginx/` — Nginx reverse proxy configs (dev, full-dev, production)
- `scrapers/` — Repository metadata scrapers (HydroShare, EarthChem, discovery)
- `jsonld/` — JSON-LD normalization examples per repository

### OCGbuildingBlockTest — OGC Building Blocks

Modular schema components following the [OGC Building Blocks](https://opengeospatial.github.io/bblocks/) pattern. Each building block is a self-contained directory with a schema, JSON-LD context, metadata, and description.

#### ADA Building Blocks

The ADA metadata schema (37 `$defs` from `adaMetadata-SchemaOrgSchema-v2.json`) has been decomposed into modular building blocks:

```
OCGbuildingBlockTest/_sources/
├── adaProperties/
│   ├── stringArray/           # Reusable string array utility type
│   ├── creativeWork/          # schema:CreativeWork labeled links
│   ├── spatialRegistration/   # Pixel coordinate system registration
│   ├── instrument/            # NXinstrument + prov:Entity analytical instruments
│   ├── laboratory/            # NXsource + schema:Place facilities
│   ├── details/               # 16 instrument-specific detail types (EMPA, XRD, NanoSIMS, etc.)
│   ├── physicalMapping/       # DDI-CDI WideDataStructure variable mapping
│   ├── image/                 # ada:image with componentType classification
│   ├── imageMap/              # Spatially registered image maps
│   ├── supDocImage/           # Supplemental document images
│   ├── tabularData/           # CDI PhysicalDataSet tabular data
│   ├── collection/            # Sets of related files
│   ├── dataCube/              # CDI DimensionalDataStructure multidimensional data
│   ├── document/              # Supplemental documents (calibration, methods, logs)
│   ├── otherFile/             # Non-standard file formats (EMSA, OBJ, STL, XLSX)
│   ├── files/                 # File-level metadata (composes all detail types above)
│   └── hasPartFile/           # Files within archive distributions
└── profiles/
    └── adaProduct/            # Top-level ADA product profile (composes all BBs)
```

Each building block directory contains:
- `bblock.json` — Metadata (name, status, tags, sources)
- `schema.yaml` — JSON Schema with `$ref` cross-references to other BBs
- `context.jsonld` — JSON-LD namespace prefix mappings
- `description.md` — Human-readable description

#### Vocabulary Namespaces

| Prefix | URI | Usage |
|---|---|---|
| `schema` | `http://schema.org/` | Core metadata properties |
| `ada` | `https://ada.astromat.org/metadata/` | ADA-specific types and properties |
| `cdi` | `http://ddialliance.org/Specification/DDI-CDI/1.0/RDF/` | Data structure descriptions |
| `prov` | `http://www.w3.org/ns/prov#` | Provenance (instruments, activities) |
| `spdx` | `http://spdx.org/rdf/terms#` | File checksums |
| `nxs` | `http://purl.org/nexusformat/definitions/` | NeXus instrument/source classes |
| `csvw` | `http://www.w3.org/ns/csvw#` | Tabular data descriptions |
| `dcterms` | `http://purl.org/dc/terms/` | Conformance declarations |

## Getting Started

### Clone

```bash
git clone --recurse-submodules https://github.com/smrgeoinfo/IEDADataSubmission.git
```

If you already cloned without `--recurse-submodules`, initialize them after the fact:

```bash
git submodule update --init --recursive
```

### Prerequisites

- Docker and docker-compose
- Python 3.10+ (for backend development)
- Node.js 20.19+ (for frontend development — required by Vite 7)

### Run the Full Stack

```bash
docker-compose -f docker-compose-upstream.yml up --build
```

Access the application at https://localhost/

### Run Backend Only (Development)

```bash
docker-compose -f docker-compose-dev.yml up --build
```

API docs at http://0.0.0.0:5002/redoc

Alternatively, use the Makefile inside `dspback/`:

```bash
cd dspback
make up
```

### Generate Schema Models

When a repository's `schema.json` is updated, regenerate the Pydantic model:

```bash
datamodel-codegen \
  --input-file-type jsonschema \
  --input dspback/dspback/schemas/ada/schema.json \
  --output dspback/dspback/schemas/ada/model.py
```

## License

Released under the BSD 3-Clause License.

This material is based upon work supported by the National Science Foundation (NSF) under awards 2012893, 2012748, and 2012593. Any opinions, findings, conclusions, or recommendations expressed in this material are those of the authors and do not necessarily reflect the views of the NSF.
