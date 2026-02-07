# Project Memory

Running log of architectural decisions and significant changes.

## 2026-02-06: Split Instrument Detail Types into Separate Building Blocks

**What changed:** The monolithic `_sources/adaProperties/details/schema.yaml` (which bundled 16 instrument-specific detail types as `$defs`) was split into 16 standalone building blocks, one per detail type.

**New directories** (under `_sources/adaProperties/`):
`detailARGT`, `detailBasemap`, `detailDSC`, `detailEAIRMS`, `detailEMPA`, `detailICPOES`, `detailL2MS`, `detailLAF`, `detailNanoIR`, `detailNanoSIMS`, `detailPSFD`, `detailQRIS`, `detailSLS`, `detailVNMIR`, `detailXCT`, `detailXRD`

Each contains: `schema.yaml`, `bblock.json`, `context.jsonld`, `description.md`.

**Why:** As the profile library expands to cover all ~97 product types in `ADA-AnalyticalMethodsAndAttributes.xlsx`, each technique profile needs to `$ref` only its specific detail type(s). Separate BBs make this possible via `$ref: ../detailXxx/schema.yaml` instead of fragile fragment pointers `../details/schema.yaml#/$defs/xyz_detail`.

**What was updated:**
- 5 referencing schemas updated to use new `$ref` paths: `tabularData`, `imageMap`, `document`, `dataCube`, `otherFile`
- `details/schema.yaml` rewritten as an umbrella schema with `anyOf` referencing all 16 new BBs
- `details/description.md` updated accordingly

**Special cases:** `detailNanoIR`, `detailNanoSIMS`, `detailPSFD` use `$ref: ../stringArray/schema.yaml` for array-valued properties — these sibling BB references remain as-is.

**Naming convention:** `detailXxx` where `Xxx` matches the uppercase technique abbreviation (e.g., `detailEMPA`, `detailXRD`, `detailNanoSIMS`). The `_detail` suffix from the old `$defs` names is dropped.

## 2026-02-07: Tabbed ADA Form UX & Compact Profile Selection

**What changed:**
1. ADA profile forms now render with tabbed navigation (5 tabs: Basic Info, Attribution, Methods & Variables, Distribution, Metadata Record) instead of a single long scroll of groups.
2. The profile selection page (`/metadata/ada`) switched from large cards in a 3-column grid to a compact `v-list` with a search/filter field — designed to scale to 80+ data types.
3. Branding renamed from "CZ Hub" to "IEDA Hub" (browser tab title, PWA manifest, vuex storage key).
4. The cors_server now sends `Cache-Control: no-cache` to prevent stale schema files during development.

**How tabs work:** The `Categorization` type is handled at the parent component level (`cz.ada-profile-form.vue`), not via a custom JSON Forms renderer. CzForm's `renderers` field is internal (not a prop), so custom renderer injection isn't possible. Instead, when the uischema root type is `Categorization`, the parent renders Vuetify `v-tabs` and passes each Category's elements as a `VerticalLayout` uischema to a separate `CzForm` instance per tab. All tabs share the same reactive `data` object. Non-Categorization schemas fall back to the original single-form rendering.

**Profile selection layout:** `cz.ada-select-type.vue` now separates the general product (always first) from analytical methods (alphabetically sorted below an "Analytical Method" divider/subheader). The `methodProfiles` array is pre-sorted alphabetically by key. The search field filters both sections by name and description.

**Files changed:**
- `dspfront/src/components/metadata/cz.ada-profile-form.vue` — Added tab detection, rendering, and state
- `dspfront/src/components/metadata/cz.ada-select-type.vue` — Compact list with search and section divider
- `dspfront/src/constants.ts` — `APP_NAME` → `'IEDA Hub'`
- `dspfront/vite.config.ts` — PWA manifest name/short_name → `'IEDA Hub'`
- `dspfront/src/modules/vuex.ts` — Vuex persisted state key → `'IEDA Hub'`
- `OCGbuildingBlockTest/_sources/jsonforms/profiles/*/uischema.json` (all 5) — Root type changed from `VerticalLayout` to `Categorization` with 5 `Category` elements
- `OCGbuildingBlockTest/tools/cors_server.py` — Added `Cache-Control: no-cache` header

**Note on vuex key change:** Changing the vuex persisted state key from `"CZ Hub"` to `"IEDA Hub"` means previously persisted local state won't carry over — users start with fresh state on first visit after this change.

## 2026-02-07: Django Catalog Backend (Milestone 1)

**What changed:** Added a new Django + DRF backend (`dspback-django/`) that coexists alongside the existing FastAPI backend (`dspback/`). This is the foundation for evolving the system from a CZHub submission tool into a profile-driven metadata catalog.

**Why:** The new catalog backend provides generic Profile and Record management — profiles are loaded from OGC Building Block build output (schema, uischema, defaults), and records store JSON-LD natively with JSON Schema validation. This decouples metadata storage from repository-specific submission logic, enabling 70+ ADA product types and other domains to be added without per-type backend code.

**Architecture:**
- Separate Django service on port 5003, separate `catalog` PostgreSQL database
- Nginx routes `/api/catalog/*` → catalog service, `/api/*` → dspback (existing)
- Zero impact on existing dspback/dspfront — complete coexistence

**New components:**
- `accounts` app — Custom User model with ORCID as `USERNAME_FIELD`, ORCID OAuth views (login/callback/logout), SimpleJWT token issuance with ORCID in `sub` claim, custom DRF auth supporting both `Authorization: Bearer` header and `?access_token=` query param
- `records` app — Profile model (schema/uischema/defaults/base_profile FK), Record model (UUID PK, JSON-LD with GIN index, extracted title/creators/identifier), JSON Schema validation (auto-detects Draft-07 vs Draft-2020-12), field extraction from JSON-LD
- `load_profiles` management command — Reads from OGC BB `build/jsonforms/profiles/`, sets parent relationships (adaEMPA/adaICPMS/adaVNMIR/adaXRD → adaProduct)

**API endpoints (all under `/api/catalog/`):**
- `GET/POST profiles/` — List/create profiles (public read, admin write)
- `GET profiles/{name}/` — Profile detail by name (returns schema+uischema+defaults)
- `GET/POST records/` — List/create records (public read, authenticated write)
- `GET/PATCH/DELETE records/{id}/` — Record CRUD (owner-only write)
- `GET records/{id}/jsonld/` — Raw JSON-LD with `application/ld+json` content type
- `POST records/import-url/`, `POST records/import-file/` — Import from URL or file upload

**Infrastructure:**
- `dspback-django/Dockerfile-dev` — Python 3.12-slim, gunicorn
- `docker-compose-dev.yml` — Added `catalog` service, mounted `OCGbuildingBlockTest` volume, added `scripts/init-catalog-db.sh` to postgres init
- `nginx/nginx-dev.conf` — Added `/api/catalog` location block before `/api`
- `.env` — Added `CATALOG_DATABASE`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`

**Setup for existing installs:** The init script only runs on fresh postgres. For existing installs: `docker exec dsp_postgres psql -U dsp -d dsp -c "CREATE DATABASE catalog OWNER dsp;"`, then `docker exec catalog python manage.py migrate` and `docker exec catalog python manage.py load_profiles`.

**Schema validation note:** The OGC BB schemas use Draft-07 (`$schema: http://json-schema.org/draft-07/schema#`). The validator auto-detects the draft version. Draft-07 lacks `unevaluatedProperties`, so strict `allOf` composition (rejecting unknown properties across composed schemas) isn't possible — typos in property names pass validation silently.
