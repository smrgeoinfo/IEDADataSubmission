# IEDA Data Submission Portal

A web application for submitting, managing, and discovering research data across multiple Earth Science repositories. This monorepo contains the backend API, frontend application, deployment configuration, and OGC Building Blocks for schema modularization.

`dspback`, `dspfront`, and `OCGbuildingBlockTest` are included as [git submodules](https://git-scm.com/book/en/v2/Git-Tools-Submodules) pointing to their respective repositories.

## Repository Structure

```
IEDADataSubmission/
├── dspback/                 # FastAPI backend (submodule → smrgeoinfo/dspback, develop)
├── dspback-django/          # Django catalog backend (profile-driven metadata records + ADA bridge)
├── dspfront/                # Vue.js frontend (submodule → smrgeoinfo/dspfront, develop)
├── OCGbuildingBlockTest/    # OGC Building Blocks (submodule → smrgeoinfo/OCGbuildingBlockTest, master)
├── scrapers/                # Repository metadata scrapers
├── jsonld/                  # JSON-LD normalization examples
├── nginx/                   # Nginx reverse proxy configs
├── scripts/                 # Infrastructure scripts (DB init, etc.)
├── docker-compose-dev.yml   # Development stack (backend + nginx)
├── docker-compose-demo.yml  # Self-contained demo stack (HTTP, all 5 services)
├── docker-compose-upstream.yml  # Full stack from source
├── docker-compose-artifact-registry.yml  # Full stack from registry
├── .env                     # Environment variables
└── .env.demo                # Demo env template (copy to .env for demo deploy)
```

## Components

### dspback — Backend API

FastAPI application providing a standardized metadata API across multiple repository types.

- **Framework:** FastAPI with async PostgreSQL (SQLAlchemy + asyncpg)
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
├── database/
│   ├── models.py           # SQLAlchemy ORM models (UserDB, SubmissionDB, RepositoryTokenDB)
│   ├── session.py          # Async engine, get_session() FastAPI dependency
│   ├── converters.py       # ORM ↔ Pydantic converters
│   └── procedures.py       # DB procedures (INSERT...ON CONFLICT upserts)
├── routers/
│   ├── ada.py              # ADA CRUD endpoints + JSON-LD ingest
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

#### Phase 2: Catalog-Driven ADA + CDIF Forms

ADA and CDIF metadata forms are driven by OGC Building Block schemas served through the Django catalog API. The frontend fetches the resolved schema, UISchema, and default values from `/api/catalog/profiles/{name}/`, renders the form with CzForm (JSON Forms), and saves records to `/api/catalog/records/`. The UISchema uses a `Categorization` root type to organize fields into tabbed sections.

```
Catalog API (dspback-django)              Frontend (dspfront)
┌──────────────────────────────────┐    ┌──────────────────────────┐
│ GET /api/catalog/profiles/{name}/│◄───│ /metadata/ada            │
│   → schema, uischema, defaults   │    │   → profile selection    │
│                                  │    │ /metadata/ada/:profile   │
│ POST /api/catalog/records/       │◄───│   → fetches profile      │
│   → validates against schema     │    │   → renders CzForm       │
│   → extracts title/creators      │    │   → saves to catalog     │
│                                  │    │ /metadata/cdif           │
│ GET /api/catalog/records/?mine   │◄───│   → same flow for CDIF   │
│   → user's catalog records       │    │                          │
└──────────────────────────────────┘    └──────────────────────────┘

My Submissions page shows both:
  • Repository Submissions tab → GET /api/submissions (dspback)
  • Catalog Records tab → GET /api/catalog/records/?mine=true (catalog)
```

Six profiles are loaded via `load_profiles`: `adaProduct` (base), `adaEMPA`, `adaXRD`, `adaICPMS`, `adaVNMIR` (technique-specific), and `CDIFDiscovery`. The profile list is fetched dynamically from the catalog API.

#### Adding a New ADA Profile

To add a new technique profile (e.g., `adaXRF`):

**1. OGC Building Block** (`OCGbuildingBlockTest/_sources/profiles/adaXRF/`)

Create the BB directory with `bblock.json`, `schema.yaml`, `context.jsonld`, and `description.md`. The `schema.yaml` should use `allOf` to extend `adaProduct` and add technique-specific `enum` constraints on `schema:additionalType` and `schema:measurementTechnique`. See an existing technique profile (e.g., `adaEMPA`) as a template.

**2. JSON Forms static files** (`OCGbuildingBlockTest/_sources/jsonforms/profiles/adaXRF/`)

Create `uischema.json` and `defaults.json`. Copy from an existing technique profile and adjust default values (e.g., `schema:additionalType`, `schema:measurementTechnique`).

**3. Schema conversion** (`OCGbuildingBlockTest/tools/convert_for_jsonforms.py`)

Add `'adaXRF'` to the `TECHNIQUE_PROFILES` list so the conversion script processes it. The generated `schema.json` will appear in `build/jsonforms/profiles/adaXRF/`.

**4. Load profile into catalog** — Run `docker exec catalog python manage.py load_profiles` to load the new profile from the BB build output. The profile list in the frontend is fetched dynamically from the catalog API, so no frontend code changes are needed for the selection page.

**5. Frontend form title** (`dspfront/src/components/metadata/geodat.ada-profile-form.vue`)

Add `adaXRF: 'ADA XRF Product Metadata'` to the `profileNames` map in the `formTitle` getter.

**6. i18n strings** (`dspfront/src/i18n/messages.ts`)

Add the profile entry under `metadata.ada.profiles`:

```ts
adaXRF: {
  name: `X-Ray Fluorescence (XRF)`,
  description: `Metadata for X-ray fluorescence datasets.`,
},
```

### dspback-django — Catalog Backend (Profile-Driven Metadata Records)

Django + DRF backend providing a generic metadata catalog API. Coexists alongside dspback during transition.

- **Framework:** Django 5.1, Django REST Framework, SimpleJWT
- **Database:** Separate `catalog` PostgreSQL database on same instance
- **Auth:** ORCID OAuth2 with SimpleJWT tokens (compatible with existing frontend)
- **Routing:** Nginx routes `/api/catalog/*` to this service (port 5003)

Profiles are loaded from OGC Building Block build output via `python manage.py load_profiles`. Records store JSON-LD natively with JSON Schema validation against the profile's schema. Person and organization entities are accumulated from saved records into `KnownPerson`/`KnownOrganization` tables, providing autocomplete pick lists via search endpoints. UISchema vocabulary configs and variable panel layouts are injected at serve time.

The `ada_bridge` app provides integration with the ADA (Astromat Data Archive) REST API — translating IEDA JSON-LD records to ADA's format, pushing them via HTTP, and syncing status/DOI back.

#### Key Catalog Backend Files

```
dspback-django/
├── manage.py
├── requirements.txt
├── Dockerfile-dev
├── catalog/                  # Django project config
│   ├── settings.py
│   ├── test_settings.py     # SQLite settings for tests
│   ├── urls.py
│   └── wsgi.py
├── accounts/                 # Auth app
│   ├── models.py            # Custom User (ORCID as USERNAME_FIELD)
│   ├── authentication.py    # JWT auth (Bearer header + ?access_token= query param)
│   ├── views.py             # ORCID OAuth login/callback/logout
│   └── adapters.py          # django-allauth ORCID adapter
├── records/                  # Core app
│   ├── models.py            # Profile, Record, KnownPerson, KnownOrganization
│   ├── serializers.py       # DRF serializers with validation hooks + vocabulary injection
│   ├── views.py             # ProfileViewSet, RecordViewSet, persons/orgs search
│   ├── validators.py        # JSON Schema validation (Draft-07 / Draft-2020-12)
│   ├── services.py          # JSON-LD field extraction, entity upsert, URL import
│   ├── uischema_injection.py # UISchema tree walker (vocabulary + variable panel layout)
│   ├── admin.py             # Django admin registration
│   ├── tests.py             # 130 tests
│   └── management/commands/
│       ├── load_profiles.py      # Load profiles from OGC BB build output
│       └── backfill_entities.py  # Populate KnownPerson/KnownOrganization from existing records
└── ada_bridge/               # ADA API integration
    ├── models.py             # AdaRecordLink (IEDA↔ADA record pair tracking)
    ├── translator_ada.py     # JSON-LD → ADA camelCase payload translation
    ├── client.py             # AdaClient — HTTP wrapper for ADA REST API
    ├── services.py           # Orchestration: push, sync, bundle introspection
    ├── bundle_service.py     # ZIP introspection via ada_metadata_forms inspectors
    ├── views.py              # DRF views: push, sync, status, bundle endpoints
    ├── urls.py               # Routes under /api/ada-bridge/
    ├── serializers.py        # Request/response serializers
    └── tests.py              # 74 tests (unit + integration)
```

#### Catalog API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/catalog/profiles/` | List all profiles |
| GET | `/api/catalog/profiles/{name}/` | Profile detail (schema, uischema, defaults) |
| GET | `/api/catalog/records/` | List records (filterable by `?profile=`, `?status=`, `?search=`, `?mine=true`) |
| POST | `/api/catalog/records/` | Create record (validates JSON-LD against profile schema) |
| GET | `/api/catalog/records/{id}/` | Record detail |
| PATCH | `/api/catalog/records/{id}/` | Update record (owner only) |
| DELETE | `/api/catalog/records/{id}/` | Delete record (owner only) |
| GET | `/api/catalog/records/{id}/jsonld/` | Raw JSON-LD (`application/ld+json`) |
| POST | `/api/catalog/records/import-url/` | Import record from URL |
| POST | `/api/catalog/records/import-file/` | Import record from file upload |
| GET | `/api/catalog/persons/?q=` | Search known persons (autocomplete pick list) |
| GET | `/api/catalog/organizations/?q=` | Search known organizations (autocomplete pick list) |
| POST | `/api/ada-bridge/push/<uuid>/` | Translate + push IEDA record to ADA |
| POST | `/api/ada-bridge/sync/<uuid>/` | Pull status + DOI from ADA |
| GET | `/api/ada-bridge/status/<uuid>/` | Get ADA link info for an IEDA record |
| POST | `/api/ada-bridge/bundle/introspect/` | Upload ZIP, return introspection results |
| POST | `/api/ada-bridge/bundle/upload/<uuid>/` | Upload bundle to linked ADA record |

#### Catalog Setup (Existing Installs)

For existing installs where postgres already has data:

```bash
docker exec dsp_postgres psql -U dsp -d dsp -c "CREATE DATABASE catalog OWNER dsp;"
docker exec catalog python manage.py migrate
docker exec catalog python manage.py load_profiles
```

Fresh installs handle database creation automatically via `scripts/init-catalog-db.sh`.

#### ADA Bridge Setup

To enable pushing records to ADA, set these environment variables:

```bash
ADA_API_BASE_URL=http://ada-api:8000   # Base URL of the ADA REST API
ADA_API_KEY=your-ada-api-key-here      # API key from ADA's Django admin
```

The bridge will work without these settings (push/sync calls will fail gracefully), so they're only needed when integrating with a running ADA instance.

### dspfront — Frontend Application

Vue.js single-page application for browsing repositories, filling metadata forms, and managing submissions.

- **Framework:** Vue 3 with TypeScript, Vuex ORM for state management
- **Form rendering:** JSON Forms (driven by backend JSON Schema + UI Schema)
- **UI Library:** Vuetify

#### Key Frontend Files

```
dspfront/src/
├── components/
│   ├── metadata/
│   │   ├── geodat.ada-select-type.vue   # ADA profile selection page (/metadata/ada)
│   │   ├── geodat.ada-profile-form.vue  # Catalog-driven ADA form (/metadata/ada/:profile)
│   │   └── geodat.cdif-form.vue         # Catalog-driven CDIF form (/metadata/cdif)
│   ├── submissions/
│   │   ├── geodat.submissions.vue       # Submissions page (repo + catalog tabs)
│   │   └── types.ts                     # EnumRepositoryKeys, IRepository, ISubmission interfaces
│   └── submit/constants.ts              # repoMetadata — name, logo, description, URLs per repo
├── services/
│   └── catalog.ts             # Catalog API helpers (fetchMyRecords, deleteRecord)
├── models/
│   ├── repository.model.ts    # Base Vuex ORM model (init, authorize, CRUD, file ops)
│   ├── ada.model.ts           # ADA repository model
│   ├── external.model.ts      # External repository model
│   ├── hydroshare.model.ts    # HydroShare model (with file/folder ops)
│   ├── earthchem.model.ts     # EarthChem model
│   ├── zenodo.model.ts        # Zenodo model
│   ├── submission.model.ts    # Submission state model
│   └── user.model.ts          # User/auth state model
├── routes.ts                  # Vue Router route definitions
└── constants.ts               # App-wide constants
```

### Deployment & Infrastructure

Docker Compose configuration and supporting services live at the repository root.

- `docker-compose-dev.yml` — Development stack (backend + nginx with SSL)
- `docker-compose-demo.yml` — Self-contained demo stack over plain HTTP (see below)
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
│   ├── details/               # Umbrella schema referencing all 16 detail type BBs
│   ├── detailARGT/            # ARGT (Argon) document detail
│   ├── detailBasemap/         # Basemap images with RGB channels and pixel scaling
│   ├── detailDSC/             # Differential Scanning Calorimetry detail
│   ├── detailEAIRMS/          # EA-IRMS collection detail
│   ├── detailEMPA/            # Electron Microprobe Analysis detail
│   ├── detailICPOES/          # ICP-OES detail
│   ├── detailL2MS/            # Laser-2 Mass Spectrometry detail
│   ├── detailLAF/             # Laser Ablation Fluorescence detail
│   ├── detailNanoIR/          # Nano-IR spectroscopy detail
│   ├── detailNanoSIMS/        # NanoSIMS detail
│   ├── detailPSFD/            # Point Spread Function Data detail
│   ├── detailQRIS/            # QRIS (Raman) detail
│   ├── detailSLS/             # Structured Light Scanning detail
│   ├── detailVNMIR/           # Very-Near Mid-IR spectroscopy detail
│   ├── detailXCT/             # X-ray Computed Tomography detail
│   ├── detailXRD/             # X-ray Diffraction detail
│   ├── physicalMapping/       # DDI-CDI WideDataStructure variable mapping
│   ├── image/                 # ada:image with componentType classification
│   ├── imageMap/              # Spatially registered image maps
│   ├── supDocImage/           # Supplemental document images
│   ├── tabularData/           # CDI PhysicalDataSet tabular data
│   ├── collection/            # Sets of related files
│   ├── dataCube/              # CDI DimensionalDataStructure multidimensional data
│   ├── document/              # Supplemental documents (calibration, methods, logs)
│   ├── otherFile/             # Non-standard file formats (EMSA, OBJ, STL, XLSX)
│   └── files/                 # File-level metadata (generic, type constraints at profile level)
└── profiles/
    └── adaProduct/            # Top-level ADA product profile (composes all BBs)
```

Each building block directory contains:
- `bblock.json` — Metadata (name, status, tags, sources, `dateOfLastChange`, `link`, etc.)
- `schema.yaml` — JSON Schema with `$ref` cross-references to other BBs (must reference `schema.yaml`, not `.json` files)
- `context.jsonld` — JSON-LD namespace prefix mappings
- `description.md` — Human-readable description
- `examples.yaml` — (optional) Example snippets with `ref:` pointing to example JSON files

A GitHub Actions workflow (`Validate and process Building Blocks`) runs on every push to validate all building blocks. A second workflow (`generate-jsonforms.yml`) runs after BB validation to generate Draft 7 JSON Forms schemas via `tools/convert_for_jsonforms.py`. See `agents.md` for detailed authoring rules.

#### JSON Forms Schema Tools

```
OCGbuildingBlockTest/tools/
├── convert_for_jsonforms.py   # Converts Draft 2020-12 → Draft 7, resolves $ref, simplifies anyOf
├── cors_server.py             # CORS-enabled HTTP server for local development
└── resolve_schema.py          # Resolves $ref in BB schemas (used by validation workflow)
```

#### JSON Forms Static Files (hand-crafted)

```
OCGbuildingBlockTest/_sources/jsonforms/profiles/
├── adaProduct/
│   ├── uischema.json    # UI layout (groups, ordering, widgets)
│   └── defaults.json    # Default values (@context, @type, empty arrays)
├── adaEMPA/
├── adaXRD/
├── adaICPMS/
├── adaVNMIR/
└── CDIFDiscovery/
```

#### JSON Forms Generated Output

```
OCGbuildingBlockTest/build/jsonforms/profiles/
├── adaProduct/schema.json    # Fully resolved Draft 7 schema
├── adaEMPA/schema.json
├── adaXRD/schema.json
├── adaICPMS/schema.json
├── adaVNMIR/schema.json
└── CDIFDiscovery/schema.json
```

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

### Demo Deployment (VPS or Local)

A self-contained stack that builds and runs all five services (nginx, frontend, backend, catalog, postgres) over plain HTTP. Suitable for a VPS demo or quick local test without SSL setup.

```bash
cp .env.demo .env
# Edit .env — set DEMO_HOST and OUTSIDE_HOST to your VPS IP or domain
docker compose -f docker-compose-demo.yml up -d --build
```

Access the application at `http://<DEMO_HOST>` (default: http://localhost).

Key differences from the dev stack:
- HTTP only (no SSL certificates needed)
- Production Dockerfiles — frontend SPA built in-container
- Named Docker volume for postgres (portable, no host path dependency)
- Catalog runs migrations automatically on startup
- Single `DEMO_HOST` variable controls the public-facing hostname

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
