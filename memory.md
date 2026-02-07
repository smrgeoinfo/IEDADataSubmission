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
