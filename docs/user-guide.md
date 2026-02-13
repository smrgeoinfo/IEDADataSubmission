# IEDA Data Submission Portal &mdash; User Guide

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
3. [Home Page](#3-home-page)
4. [Navigation](#4-navigation)
5. [Create Metadata (Geochemical Datasets)](#5-create-metadata-geochemical-datasets)
6. [Register Dataset (CDIF)](#6-register-dataset-cdif)
7. [Submit Data](#7-submit-data)
8. [ADA Bundle Wizard](#8-ada-bundle-wizard)
9. [Update Existing Metadata](#9-update-existing-metadata)
10. [My Submissions](#10-my-submissions)
11. [Find the Right Repository](#11-find-the-right-repository)
12. [Account & Settings](#12-account--settings)
13. [Resources](#13-resources)
14. [Tips & Troubleshooting](#14-tips--troubleshooting)

---

## 1. Introduction

The **IEDA Earth Science Data Submission Portal** helps researchers submit, describe, and manage earth science data and research products. The portal provides:

- **Standardized metadata forms** for geochemical analytical datasets (ADA profiles) and general dataset registration (CDIF).
- **Direct submission** to supported repositories (HydroShare, EarthChem).
- **Bundle-based submission** to the Astromaterials Data Archive (ADA) via an upload-and-introspect wizard.
- A **repository recommendation system** to help you decide where to submit your data.
- Tools for **updating existing metadata** records by DOI, file upload, or URL.

The portal follows FAIR data principles (Findable, Accessible, Interoperable, Reusable) and is operated by IEDA2, a collaborative data infrastructure of EarthChem, LEPR/traceDs, and SESAR.

---

## 2. Getting Started

### Logging In

The portal uses **ORCID** for authentication. You do not create a separate account.

1. Click the **Log In** button in the top-right corner of the navigation bar (or on the home page banner).
2. A dialog explains that the portal uses your ORCID iD.
3. Click **Log In Using ORCID**. You will be redirected to the ORCID website.
4. Sign in with your ORCID credentials (or register for a free ORCID iD at [orcid.org](https://orcid.org) if you don't have one).
5. Authorize the portal to access your ORCID profile.
6. You are returned to the portal and logged in.

### What Requires Login

Most pages are viewable without logging in, but the following actions require authentication:

- Creating or editing metadata records
- Submitting data to repositories
- Using the ADA Bundle Wizard
- Viewing your submissions
- Updating existing metadata
- Accessing Account & Settings

If you try to access a protected page while not logged in, the portal will prompt you to log in first.

---

## 3. Home Page

The home page is the portal's landing page. It has three main sections:

### Banner

A large header reading **"Earth Science Data Submission Portal"**. If you are not logged in, a **Log In** button is displayed.

### Action Cards

Below the banner, you see the heading **"What do you want to do?"** with five action cards:

| Card | Description | Destination |
|------|-------------|-------------|
| **Create Metadata for Geochemical Dataset** | Generate standardized metadata for analytical geochemistry datasets using community-defined templates. | Profile selection page (`/metadata/ada`) |
| **Submit Data Products** | Assemble your data files and metadata using templates and submit directly to a supported repository. | Submit Data landing page (`/submit`) |
| **Find the Right Repository** | Use the repository recommendation system to find the best place for your data. | Repository Recommendations questionnaire (`/resources/recommendations`) |
| **Register Dataset** | Register a dataset with CDIF discovery metadata to make it findable across catalogs and repositories. | CDIF metadata form (`/metadata/cdif`) |
| **Register Samples** | Register metadata for samples and get an IGSN. | Opens the external SESAR website ([geosamples.org](https://www.geosamples.org/)) |

### FAIR Data & Supported Repositories

Below the action cards, the page describes the FAIR data principles and lists the portal's supported repositories:

- **Direct submission**: HydroShare, EarthChem
- **Sample registration**: SESAR (external link)
- **External repositories**: ESS-DIVE, EDI, Zenodo, ScienceBase, OpenTopography (datasets submitted to these can be registered in the portal for discoverability)

---

## 4. Navigation

### Desktop Navigation Bar

On larger screens, the top navigation bar contains these buttons (left to right):

| Button | Page |
|--------|------|
| **Home** | Home page |
| **My Submissions** | Your submission and catalog records list |
| **Resources** | Quick Start Guide, recommendations, best practices |
| **Submit Data** | Repository submission landing page |
| **Create Metadata** | Geochemical metadata profile selection |
| **Register Dataset** | CDIF Discovery metadata form |
| **Find Repository** | Repository recommendation questionnaire |
| **About** | About IEDA2 and the portal |
| **Contact** | How to contact the IEDA team |

On the right side of the navigation bar:

- **Log In** button (if not logged in)
- **Account menu** (if logged in) &mdash; a user icon with a dropdown containing:
  - **Account & Settings** &mdash; goes to your profile page
  - **Log Out** &mdash; logs you out (with confirmation dialog)

### Mobile Navigation

On smaller screens (tablets and phones), the navigation buttons are replaced by a **hamburger menu icon**. Tapping it opens a side drawer listing all the same pages plus the Log In / Account options.

---

## 5. Create Metadata (Geochemical Datasets)

### Profile Selection Page

**URL:** `/metadata/ada`

This page is titled **"Create Metadata for Geochemical Dataset"** and lets you choose the type of analytical dataset you want to describe. Each profile provides a tailored metadata form.

**How it works:**

1. A searchable list displays all available profiles, organized into sections:
   - **General Geochemical Product** (`adaProduct`) &mdash; always listed first. Use this for datasets that don't fit a specific technique.
   - **Analytical Method** &mdash; 35 technique-specific profiles (e.g., Electron Microprobe Analysis, ICP Mass Spectrometry, Raman Spectroscopy).
   - **CDIF Profiles** &mdash; specialized CDIF profiles (e.g., X-Ray Absorption Spectroscopy).
2. Use the **Filter data types...** search box to narrow the list by name or description.
3. Click a profile to open its metadata form.

### Available Technique Profiles

The portal currently supports these analytical techniques (each with its own tailored form):

- AI-driven Visual Analysis (AIVA)
- Accelerator Mass Spectrometry (AMS)
- Argon Geochronology and Thermochronology (ARGT)
- Differential Scanning Calorimetry (DSC)
- Electron Microprobe Analysis (EMPA)
- Elemental Analysis - Isotope Ratio Mass Spectrometry (EA-IRMS)
- Fourier Transform Ion Cyclotron Resonance Mass Spectrometry (FTICR-MS)
- Gas Chromatography Mass Spectrometry (GC-MS)
- Gas Pycnometry (GPYC)
- ICP Mass Spectrometry (ICP-MS)
- Inductively Coupled Plasma Optical Emission Spectrometry (ICP-OES)
- Ion Chromatography (IC)
- Laser-Assisted Fluorination (LAF)
- Liquid Chromatography Mass Spectrometry (LC-MS)
- Lock-In Thermography (LIT)
- Nano-Infrared Spectroscopy (NanoIR)
- Nanoscale Secondary Ion Mass Spectrometry (NanoSIMS)
- Noble Gas and Nitrogen Static Mass Spectrometry (NG-NS-MS)
- Particle Size-Frequency Distribution (PSFD)
- Quantitative Reflectance Imaging Spectroscopy (QRIS)
- Raman Spectroscopy (RAMAN)
- Resonance Ionization Time-of-Flight Noble Gas Mass Spectrometry (RI-TOF-NGMS)
- Scanning Electron Microscopy (SEM)
- Secondary Ion Mass Spectrometry (SIMS)
- Seismic Velocities and Rock Ultrasonic Elastic Constants (SV-RUEC)
- Structured Light Scanning (SLS)
- Time-of-Flight Secondary Ion Mass Spectrometry (ToF-SIMS)
- Transmission Electron Microscopy (TEM)
- Two-Step Laser Mass Spectrometry (L2MS)
- Ultraviolet Fluorescence Microscopy (UVFM)
- Visible Light Microscopy (VLM)
- Visible-Near-Mid Infrared Spectroscopy (VNMIR)
- X-Ray Absorption Near Edge Structure (XANES)
- X-Ray Computed Tomography (XCT)
- X-Ray Diffraction (XRD)

### The Metadata Form

**URL:** `/metadata/ada/:profile` (e.g., `/metadata/ada/adaEMPA`)

After selecting a profile, you are taken to the metadata form. The form is generated dynamically from the profile's JSON Schema and UI Schema.

**Key elements of the form page:**

- **Title**: Shows the profile name (e.g., "Electron Microprobe Analysis (EMPA)").
- **Instructions alert**: Reminds you to fill in required fields (marked with `*` and highlighted in red).
- **ADA Status banner** (if the record has been pushed to ADA): Shows the ADA processing status and DOI if assigned.
- **Tabs**: For complex profiles, the form may be organized into tabs (e.g., "Product", "Distribution", "Variables").

**Toolbar buttons (at the top and bottom of the form):**

| Button | Action |
|--------|--------|
| **Load from File** | Upload a JSON file to populate the form with existing metadata. |
| **Cancel** | Return to the My Submissions page without saving. |
| **Save** / **Save Changes** | Save the metadata record to the portal's catalog. This does NOT submit to ADA. |
| **Submit to ADA** | (ADA profiles only) First save, then push the record to the Astromaterials Data Archive. This button is only enabled after the record has been saved at least once, and there are no unsaved changes. |

**Working with the form:**

- Required fields are marked with an asterisk (`*`) and highlighted.
- Hover over a field to see its description/hint.
- For distribution (file) information, expand sections for Image, Tabular, Data Cube, and Document file types. Fields appear or disappear based on the selected MIME type and component type.
- Variables can be added to describe measurements in your dataset.

**Save vs. Submit to ADA:**

- **Save** stores your metadata locally in the portal catalog. You can return to edit it later from the My Submissions page.
- **Submit to ADA** saves locally first, then transmits the metadata to the Astromaterials Data Archive. Once submitted, the record receives an ADA status and eventually a DOI.

---

## 6. Register Dataset (CDIF)

**URL:** `/metadata/cdif`

This page is titled **"Register Dataset with CDIF Metadata"**. Use it to create a CDIF Discovery metadata record that makes your dataset findable across catalogs and repositories. This is useful when your data has already been submitted to another repository and you want to register it for broader discoverability.

**How it works:**

1. The page displays a form generated from the CDIF Discovery profile schema.
2. Fill in the required fields (marked with `*`).
3. You can use the **Load from File** button to populate the form from an existing JSON file.
4. Click **Save** to create the record in the portal catalog.
5. Use **Cancel** to return without saving.

The form may be organized into tabs depending on the schema complexity (e.g., "General", "Distribution", "Spatial").

---

## 7. Submit Data

**URL:** `/submit`

The Submit Data page is a landing page for all data submission options.

### Banner

A banner reading **"Submit Data"** with a **"Help Me Decide"** button that takes you to the repository recommendation questionnaire.

### Repository Cards

Below the banner, the page shows cards for each submission option:

| Card | Description |
|------|-------------|
| **Astromaterials Data Archive (ADA)** | Upload a data bundle (ZIP), introspect file contents, fill metadata forms, and push to ADA. Opens the [ADA Bundle Wizard](#8-ada-bundle-wizard). |
| **HydroShare** | Submit directly to HydroShare (requires HydroShare authorization). |
| **EarthChem** | Submit directly to EarthChem Library (requires EarthChem authorization). |
| **Register Samples** | Opens the SESAR website for sample registration. |
| **Register Dataset** | Register a dataset from another repository using CDIF Discovery metadata. Goes to the [CDIF form](#6-register-dataset-cdif). |
| **Update Existing Metadata** | Fetch and update an existing record by DOI, file, or URL. Goes to the [Update Metadata page](#9-update-existing-metadata). |

### Direct Repository Submission (HydroShare / EarthChem)

When you click a supported repository card:

1. If you are not logged in, you will be prompted to log in.
2. If you have not authorized the portal to access the repository, an authorization dialog appears. Follow the prompts to authorize access.
3. Once authorized, you are taken to the submission form for that repository.
4. The form allows you to fill in metadata and upload files.
5. Use **Save** to save a draft or **Finish** to complete the submission.

---

## 8. ADA Bundle Wizard

**URL:** `/bundle-wizard`

The ADA Bundle Wizard is a multi-step workflow for uploading a data bundle, reviewing its contents, filling in metadata, and submitting to the Astromaterials Data Archive. It consists of up to 5 steps.

### Step 1: Upload

Upload your data bundle using one of three methods:

| Tab | How It Works |
|-----|-------------|
| **Upload File** | Drag and drop a ZIP file onto the drop zone, or click **Browse Files** to select one. |
| **From URL** | Paste a URL pointing to a ZIP bundle file. |
| **Local Directory** | Click **Browse Folder** to select a local folder, or drag and drop a folder. The portal will automatically zip the folder contents before uploading. |

After selecting your data, click **Upload & Introspect**. The portal uploads your bundle and analyzes its contents (file types, sizes, any product metadata files).

**What happens next depends on whether a `product.yaml` file is found:**

- **If found**: The wizard skips to Step 3 (File Review) since the product metadata is already available.
- **If not found**: A dialog appears listing any YAML files in the bundle. You can either:
  - Select one of those YAML files to use as product metadata, or
  - Click **Skip &mdash; Enter Manually** to go to Step 2.

### Step 2: Product Info (Conditional)

This step only appears if no `product.yaml` was found (or you chose to skip the YAML picker).

Fill in the product metadata manually:

| Field | Description |
|-------|-------------|
| **Title** * | Title of the data product. |
| **Description** * | Brief description of what the data product contains. |
| **Keywords** | Comma-separated keywords for discoverability. |
| **License** | License for the data (e.g., CC-BY-4.0). |
| **Creators** | One or more creators with name and optional ORCID. Click **+ Add Creator** to add more. |
| **Funding References** | Optional funding information (funder name, award number, award title). |

Click **Save & Continue** to proceed. Click **Back** to return to Step 1.

### Step 3: File Review

This step shows a table of all files detected in your bundle. For each file you can see and edit:

| Column | Description |
|--------|-------------|
| **Include** | Checkbox to include or exclude the file from the submission. |
| **Filename** | The file's path within the bundle. |
| **MIME Type** | Auto-detected file type (editable dropdown &mdash; you can correct it if misidentified). |
| **Size** | File size. |
| **Inspection Summary** | Auto-generated summary of the file's contents (e.g., number of rows/columns for CSV files). |
| **Component Type** | What kind of data the file represents (e.g., DataTable, Image, Micrograph). Options change based on the MIME type. |

Review the file list, correct any MIME types or component types if needed, and uncheck files you don't want to include. Then click **Continue**.

### Step 4: Metadata Form

This step presents the full metadata form for your dataset.

1. **Select a profile**: Choose a metadata profile from the dropdown (e.g., `adaEMPA`, `adaXRD`, `adaProduct`). Click **Load Form** to load the schema.
2. **Fill in the form**: The form is the same as the standalone metadata form (see [Section 5](#5-create-metadata-geochemical-datasets)). It may be organized into tabs.
3. **Auto-populated fields**: Some fields may be pre-filled from the product YAML and file introspection data (titles, descriptions, file information).
4. **Load from File**: You can load existing metadata from a JSON file.
5. **Add Variables**: Use the **New Variable** button (if visible) to add variables describing measurements in your dataset. Each variable has a name, description, and optional unit.
6. **Change Profile**: Click **Change Profile** to switch to a different metadata profile.

Click **Continue** when the form is complete. Click **Back** to return to the File Review step.

### Step 5: Review & Submit

This final step displays a summary of your submission:

- **Title** and **Description** from the metadata
- **Profile** used
- **Creators** listed as chips
- **Included Files** with their component types
- **Variables** if any were defined

Two submission options are available:

| Button | Action |
|--------|--------|
| **Save to Catalog** | Saves the metadata record to the portal catalog only. You can push to ADA later from the My Submissions page. |
| **Save & Push to ADA** | Saves to the catalog and immediately transmits the metadata to the Astromaterials Data Archive. |

After successful submission, you are redirected to the **My Submissions** page and a success notification is shown.

---

## 9. Update Existing Metadata

**URL:** `/metadata/update`

This page lets you fetch and edit an existing metadata record. It offers three methods via tabs:

### By DOI

1. Enter a DOI (e.g., `10.xxxxx/example`) in the text field.
2. Click **Fetch Record**.
3. The portal retrieves the record from ADA using the DOI.

### From Local File

1. Click **Choose File** and select a JSON-LD (`.json` or `.jsonld`) file from your computer.
2. The portal parses the file and loads the metadata.

### From URL

1. Enter a URL pointing to a JSON-LD metadata document.
2. Click **Fetch Metadata**.
3. The portal downloads and parses the metadata.

### After Loading

Once metadata is loaded from any of the three methods:

1. The portal **auto-detects the matching profile** based on the metadata content (from `conformsTo` URIs, `schema:additionalType` values, or measurement technique codes). An info alert shows which field was used for detection.
2. A **Metadata Profile** dropdown lets you confirm or change the detected profile.
3. Click **Open in Form** to create a draft catalog record and navigate to the full metadata form where you can edit and save.

---

## 10. My Submissions

**URL:** `/submissions`

This page shows all your data submissions and catalog records. It has two tabs:

### Repository Submissions Tab

Lists submissions made through repository integrations (HydroShare, EarthChem, external registrations).

**Features:**

- **Search**: Filter submissions by text (title, authors, identifier).
- **Repository filter**: Filter by repository (multi-select dropdown).
- **Sort**: Sort by date, title, or other fields, in ascending or descending order.
- **Pagination**: Navigate through pages of results. Adjust items per page.
- **Export Submissions**: Download a CSV file of your filtered submissions (Authors, Publication Date, Title, Repository, URL).

**Each submission card shows:**

- Title
- Authors
- Submission Repository
- Submission Date
- Identifier
- Type (for HydroShare resources)
- Status (for EarthChem submissions: incomplete, submitted, published)

**Actions per submission:**

| Button | Action |
|--------|--------|
| **View In Repository** | Opens the submission in its repository in a new browser tab. |
| **Edit** | Opens the submission form to edit (available if not published, not an EarthChem submitted/published record, and the repository supports form editing). |
| **Update Record** | Re-fetches the latest data from the repository to update the portal's copy. |
| **Delete** | Deletes the submission metadata from the portal. A confirmation dialog appears with an option to also delete the resource from the repository (if supported and the resource is not published). |

### Catalog Records Tab

Lists metadata records saved in the portal's catalog (from the ADA metadata forms, CDIF forms, or the Bundle Wizard).

**Each record shows:**

- Title
- Creators
- Profile name
- Status (draft, published, deprecated)
- ADA Status (if pushed to ADA: pushed, processed, error)
- ADA DOI (if assigned)
- Last updated date

**Actions per record:**

| Button | Action |
|--------|--------|
| **Edit** | Opens the metadata form for editing. CDIF records open in the CDIF form; ADA records open in the appropriate technique profile form. |
| **Push to ADA** / **Re-push to ADA** | (ADA records only) Submits or re-submits the record to the Astromaterials Data Archive. |
| **View JSON-LD** | Opens the raw JSON-LD metadata in a new tab. |
| **Delete** | Permanently deletes the catalog record (with confirmation dialog). |

### New Submission Button

A **New Submission** speed-dial button at the top offers quick access to create new submissions:

- **HydroShare** &mdash; starts a new HydroShare submission
- **EarthChem** &mdash; starts a new EarthChem submission
- **Register Dataset** &mdash; opens the CDIF metadata form

---

## 11. Find the Right Repository

**URL:** `/resources/recommendations`

This page provides a **Repository Recommendations** questionnaire to help you determine where to submit your data.

**How it works:**

1. Read the introductory text. Note that some partnership agreements or journal requirements may dictate a specific repository.
2. A vertical stepper walks you through questions about your data type.
3. At each step, select the radio button that best describes your data.
4. The stepper advances to the next question based on your answer.
5. At the end, you receive a recommendation for which repository to use, along with relevant links.
6. You can go back and change answers at any step by clicking on a previous step.

The questionnaire covers common earth science data types and directs you to HydroShare, EarthChem, SESAR, or other appropriate repositories.

---

## 12. Account & Settings

**URL:** `/profile`

Accessible from the user menu (account icon) in the navigation bar. The profile page has two sub-pages:

### Account

**URL:** `/profile/account`

Shows your ORCID-based access token. This token is used internally by the portal and can be copied (via the copy icon) if you need it for API access.

### Authorized Repositories

**URL:** `/profile/authorized-repositories`

Lists the repositories the portal can interact with on your behalf. For each repository:

- **Status**: Shows whether you have authorized the portal (green "Authorized" chip or red "Unauthorized" chip).
- **Authorize button**: If not authorized, click **Authorize** to open the repository's authorization flow.
- **Revoke button**: If authorized, click **Revoke** to remove the portal's access to that repository.
- **Access token**: When authorized, your repository access token is displayed and can be copied.

Repositories that require authorization include HydroShare and EarthChem.

---

## 13. Resources

**URL:** `/resources`

The Resources page provides links to helpful materials:

### Quick Start Guide

A step-by-step guide for getting started with the portal. Click the **Quick Start Guide** button to view it.

### Repository Recommendations

A link to the [repository recommendation questionnaire](#11-find-the-right-repository). Click **Help Me Decide** to begin.

### Best Practices and Data Templates

Links to external best practice documents and data templates for various earth science data types, including:

- Best Practices for All CZ Net Data
- Data type-specific guides (geochemistry, hydrology, etc.)
- Template files for common data formats

---

## 14. Tips & Troubleshooting

### Required Fields

- Required fields are marked with an asterisk (`*`) and highlighted in red when empty.
- You must fill all required fields before the **Save** button becomes active (for CDIF forms) or before submitting to ADA.
- ADA metadata forms allow saving with incomplete required fields (as a draft), but you must complete all required fields before using **Submit to ADA**.

### Loading Existing Data

- Use **Load from File** on any metadata form to populate it with data from a JSON file.
- Use the **Update Existing Metadata** page to fetch records by DOI, file upload, or URL.
- The portal will attempt to auto-detect the correct profile for imported metadata.

### Browser Compatibility

- The portal works best in modern browsers (Chrome, Firefox, Edge, Safari).
- The local directory upload feature in the Bundle Wizard uses browser file APIs that work in Chrome and Edge. Firefox and Safari may have limited directory drag-and-drop support.

### Common Issues

| Issue | Solution |
|-------|----------|
| "You need to log in to view this page" | Click **Log In** in the navigation bar and authenticate with ORCID. |
| Authorization dialog keeps appearing | Complete the repository authorization flow. Check the Authorized Repositories page under Account & Settings. |
| Submit to ADA button is disabled | Make sure you have saved the record first (no unsaved changes). The button is only enabled for saved records. |
| Cannot edit a submission | Published resources and submitted EarthChem records cannot be edited. HydroShare collections also cannot be edited through the portal. |
| File upload fails in Bundle Wizard | Ensure the file is a valid ZIP archive. For URL uploads, verify the URL points directly to a ZIP file. |
| Profile auto-detection is wrong | After loading metadata via the Update page, you can manually change the profile in the dropdown before clicking "Open in Form". |
| Form fields are not visible | Some fields only appear when certain conditions are met (e.g., file-type-specific fields appear only when a matching MIME type is selected). |

### Getting Help

- Visit the **Contact** page for information on how to reach the IEDA team.
- Report issues on the portal's GitHub repository: [github.com/smrgeoinfo/IEDADataSubmission/issues](https://github.com/smrgeoinfo/IEDADataSubmission/issues)
