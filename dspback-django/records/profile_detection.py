"""Detect the best-matching metadata profile from JSON-LD content."""

# -- Mapping: ada: product type -> profile name --
# Product types appear in root-level schema:additionalType.
# Original 4 profiles (from their schema.yaml contains.enum):
# Generated 31 profiles (from generate_profiles.py product_types, prefixed with ada:).
PRODUCT_TYPE_TO_PROFILE = {
    # adaEMPA
    "ada:EMPAImage": "adaEMPA",
    "ada:EMPACollection": "adaEMPA",
    "ada:EMPAQEA": "adaEMPA",
    "ada:EMPAESPC": "adaEMPA",
    # adaXRD
    "ada:XRDTabular": "adaXRD",
    "ada:XRDDiffractionPattern": "adaXRD",
    "ada:XRDIndexedImage": "adaXRD",
    # adaICPMS
    "ada:HRICPMSProcessed": "adaICPMS",
    "ada:HRICPMSRaw": "adaICPMS",
    "ada:QICPMSProcessedTabular": "adaICPMS",
    "ada:QICPMSRawTabular": "adaICPMS",
    "ada:MCICPMSTabular": "adaICPMS",
    "ada:MCICPMSCollection": "adaICPMS",
    "ada:MCICPMSRaw": "adaICPMS",
    # adaVNMIR
    "ada:VNMIRSpectralPoint": "adaVNMIR",
    "ada:VNMIROverviewImage": "adaVNMIR",
    "ada:VNMIRSpectralMap": "adaVNMIR",
    "ada:VNMIRSpectraPlot": "adaVNMIR",
    # 31 generated profiles (ada: + product_types from generate_profiles.py)
    "ada:ARGTDocument": "adaARGT",
    "ada:ARGTCollection": "adaARGT",
    "ada:DSCHeatTabular": "adaDSC",
    "ada:DSCResultsTabular": "adaDSC",
    "ada:EAIRMSCollection": "adaEAIRMS",
    "ada:ICPOESIntermediateTabular": "adaICPOES",
    "ada:ICPOESProcessedTabular": "adaICPOES",
    "ada:ICPOESRawTabular": "adaICPOES",
    "ada:L2MSCube": "adaL2MS",
    "ada:L2MSOverviewImage": "adaL2MS",
    "ada:LAFProcessed": "adaLAF",
    "ada:LAFRaw": "adaLAF",
    "ada:NanoIRBackground": "adaNanoIR",
    "ada:NanoIRMap": "adaNanoIR",
    "ada:NanoIRMapCollection": "adaNanoIR",
    "ada:NanoIRPointCollection": "adaNanoIR",
    "ada:NanoSIMSCollection": "adaNanoSIMS",
    "ada:NanoSIMSImageCollection": "adaNanoSIMS",
    "ada:NanoSIMSTabular": "adaNanoSIMS",
    "ada:NanoSIMSMap": "adaNanoSIMS",
    "ada:NanoSIMSImage": "adaNanoSIMS",
    "ada:PSFDTabular": "adaPSFD",
    "ada:QRISCalibratedCollection": "adaQRIS",
    "ada:QRISRawCollection": "adaQRIS",
    "ada:QRISCalibrationFile": "adaQRIS",
    "ada:SLSShapeModel": "adaSLS",
    "ada:SLSPartialScan": "adaSLS",
    "ada:ShapeModelImage": "adaSLS",
    "ada:XCTImageCollection": "adaXCT",
    "ada:AIVAImage": "adaAIVA",
    "ada:AIVAImageCollection": "adaAIVA",
    "ada:AMSRawData": "adaAMS",
    "ada:AMSProcessedData": "adaAMS",
    "ada:FTICRMSTabular": "adaFTICRMS",
    "ada:FTICRMSCube": "adaFTICRMS",
    "ada:GCMSCollection": "adaGCMS",
    "ada:GCMSCube": "adaGCMS",
    "ada:GCGCMSCollection": "adaGCMS",
    "ada:GPYCProcessedTabular": "adaGPYC",
    "ada:GPYCRawTabular": "adaGPYC",
    "ada:ICTabular": "adaIC",
    "ada:LCMSCollection": "adaLCMS",
    "ada:LCMSMSCollection": "adaLCMS",
    "ada:LITImage": "adaLIT",
    "ada:LIT2DDataCollection": "adaLIT",
    "ada:LITPolarDataCollection": "adaLIT",
    "ada:NGNSMSRaw": "adaNGNSMS",
    "ada:NGNSMSProcessed": "adaNGNSMS",
    "ada:RAMANRawTabular": "adaRAMAN",
    "ada:RITOFNGMSTabular": "adaRITOFNGMS",
    "ada:RITOFNGMSCollection": "adaRITOFNGMS",
    "ada:SEMImageCollection": "adaSEM",
    "ada:SEMImageMap": "adaSEM",
    "ada:SEMEBSDGrainImage": "adaSEM",
    "ada:SEMEBSDGrainImageMap": "adaSEM",
    "ada:SEMEBSDGrainImageMapCube": "adaSEM",
    "ada:SEMEDSElementalMap": "adaSEM",
    "ada:SEMEDSElementalMaps": "adaSEM",
    "ada:SEMEDSElementalMapsCube": "adaSEM",
    "ada:SEMEDSPointData": "adaSEM",
    "ada:SEMEDSPointDataCollection": "adaSEM",
    "ada:SEMEDSPointDataCube": "adaSEM",
    "ada:SEMHRCLImage": "adaSEM",
    "ada:SEMHRCLMap": "adaSEM",
    "ada:SEMHRCLCube": "adaSEM",
    "ada:SIMSTabular": "adaSIMS",
    "ada:SIMSCollection": "adaSIMS",
    "ada:SVRUECTabular": "adaSVRUEC",
    "ada:TEMImage": "adaTEM",
    "ada:TEMPatternsImage": "adaTEM",
    "ada:TEMEDSImageCollection": "adaTEM",
    "ada:STEMImage": "adaTEM",
    "ada:STEMEDSTabular": "adaTEM",
    "ada:STEMEDSCube": "adaTEM",
    "ada:STEMEDSTomo": "adaTEM",
    "ada:STEMEELSTabular": "adaTEM",
    "ada:STEMEELSCube": "adaTEM",
    "ada:TOFSIMSCollection": "adaToFSIMS",
    "ada:UVFMImage": "adaUVFM",
    "ada:UVFMImageCollection": "adaUVFM",
    "ada:VLMImage": "adaVLM",
    "ada:VLMImageCollection": "adaVLM",
    "ada:XANESImageStack": "adaXANES",
    "ada:XANESStackOverviewImage": "adaXANES",
    "ada:XANESRawTabular": "adaXANES",
    "ada:XANESProcessedTabular": "adaXANES",
    "ada:XANESimage": "adaXANES",
    "ada:XANESCollection": "adaXANES",
}

# -- Mapping: human-readable labels -> profile (from adaProduct schema enum + generate_profiles.py) --
ADDITIONAL_TYPE_LABEL_TO_PROFILE = {
    "40Ar/39Ar geochronology and thermochronology": "adaARGT",
    "Accelerator Mass Spectrometry": "adaAMS",
    "Advanced Imaging & Visualization of Astromaterials": "adaAIVA",
    "Advanced Imaging &amp; Visualization of Astromaterials": "adaAIVA",
    "Differential Scanning Calorimetry": "adaDSC",
    "Electron Microprobe Analysis": "adaEMPA",
    "Elemental analysis - isotope ratio mass spectrometry": "adaEAIRMS",
    "Fourier Transform Ion Cyclotron Resonance Mass Spectrometry": "adaFTICRMS",
    "Gas Chromatography-Mass Spectrometry": "adaGCMS",
    "Gas pycnometry": "adaGPYC",
    "Inductively coupled plasma - optical emission spectrometry": "adaICPOES",
    "Ion Chromatography": "adaIC",
    "Laser Assisted Fluorination for Bulk Oxygen Isotope Ratio Measurements": "adaLAF",
    "Liquid chromatography-mass spectrometry": "adaLCMS",
    "Lock-In Thermography": "adaLIT",
    "Microprobe Two-Step Laser Mass Spectrometry": "adaL2MS",
    "Nanoscale Infrared Mapping": "adaNanoIR",
    "Nanoscale secondary ion mass spectrometry": "adaNanoSIMS",
    "Noble gas and Nitrogen Static Mass Spectrometry": "adaNGNSMS",
    "Particle Size Frequency Distribution": "adaPSFD",
    "Quantitative Reflectance Imaging System": "adaQRIS",
    "Raman vibrational spectroscopy": "adaRAMAN",
    "Resonance ionization time of flight noble gas mass spectrometry": "adaRITOFNGMS",
    "Scanning electron microscopy": "adaSEM",
    "Secondary ion mass spectrometry": "adaSIMS",
    "Seismic Velocities and Rock Ultrasonic Elastic Constants": "adaSVRUEC",
    "Structured Light Scanning": "adaSLS",
    "Time-of-flight secondary ion mass spectrometry": "adaToFSIMS",
    "Transmission Electron Microscopy": "adaTEM",
    "Ultraviolet Fluorescence Microscopy": "adaUVFM",
    "Visible Light Microscopy": "adaVLM",
    "Visible, near-infrared, and mid-infrared Spectroscopy": "adaVNMIR",
    "X-ray Absorption Near Edge Structure": "adaXANES",
    "X-ray computed tomography": "adaXCT",
    "X-ray Diffraction": "adaXRD",
}

# -- Mapping: termCode -> profile (same as validate_instance.py) --
TERMCODE_TO_PROFILE = {
    "AIVA": "adaAIVA", "AMS": "adaAMS", "ARGT": "adaARGT",
    "DSC": "adaDSC", "EA-IRMS": "adaEAIRMS", "EMPA": "adaEMPA",
    "FIB-SEM": "adaSEM", "FTICR-MS": "adaFTICRMS", "GC-MS": "adaGCMS",
    "GPYC": "adaGPYC", "HR-ICP-MS": "adaICPMS", "IC": "adaIC",
    "ICP-OES": "adaICPOES", "LAF": "adaLAF", "LC-MS": "adaLCMS",
    "LIT": "adaLIT", "MC-ICP-MS": "adaICPMS", "NanoIR": "adaNanoIR",
    "NanoSIMS": "adaNanoSIMS", "NG-NS-MS": "adaNGNSMS",
    "PSFD": "adaPSFD", "Q-ICP-MS": "adaICPMS", "QRIS": "adaQRIS",
    "RAMAN": "adaRAMAN", "RI-TOF-NGMS": "adaRITOFNGMS",
    "SEM": "adaSEM", "SIMS": "adaSIMS", "SLS": "adaSLS",
    "SV-RUEC": "adaSVRUEC", "TEM": "adaTEM", "ToF-SIMS": "adaToFSIMS",
    "uL2MS": "adaL2MS", "UVFM": "adaUVFM", "VLM": "adaVLM",
    "VLMBasemap": "adaVLM", "VNMIR": "adaVNMIR", "XANES": "adaXANES",
    "XCT": "adaXCT", "XRD": "adaXRD",
}

_PROFILE_PREFIXES = ("ada:profile/", "https://ada.astromat.org/metadata/profile/")


def detect_profile(jsonld: dict) -> dict:
    """Detect profile from JSON-LD. Returns {"profile": name, "source": method} or {"profile": None}."""

    # 1. conformsTo
    subject_of = jsonld.get("schema:subjectOf", {})
    if not isinstance(subject_of, dict):
        subject_of = {}
    conforms_to = subject_of.get("dcterms:conformsTo", [])
    if not isinstance(conforms_to, list):
        conforms_to = [conforms_to]
    for entry in conforms_to:
        uri = entry.get("@id", "") if isinstance(entry, dict) else str(entry)
        for prefix in _PROFILE_PREFIXES:
            if uri.startswith(prefix):
                return {"profile": uri[len(prefix):], "source": "conformsTo"}

    # 2. schema:additionalType
    additional_types = jsonld.get("schema:additionalType", [])
    if isinstance(additional_types, str):
        additional_types = [additional_types]
    for val in additional_types:
        if val == "ada:DataDeliveryPackage":
            continue
        # Check ada: product types
        profile = PRODUCT_TYPE_TO_PROFILE.get(val)
        if profile:
            return {"profile": profile, "source": "additionalType"}
        # Check human-readable labels (substring match for partial labels in data)
        for label, prof in ADDITIONAL_TYPE_LABEL_TO_PROFILE.items():
            if label in val or val in label:
                return {"profile": prof, "source": "additionalType"}

    # 3. termCode
    mt = jsonld.get("schema:measurementTechnique", {})
    if isinstance(mt, dict):
        term_code = mt.get("schema:termCode", "")
        profile = TERMCODE_TO_PROFILE.get(term_code)
        if profile:
            return {"profile": profile, "source": "termCode"}

    return {"profile": None, "source": None}
