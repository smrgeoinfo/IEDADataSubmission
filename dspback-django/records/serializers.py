import copy
import json
import re
import uuid
from datetime import datetime, timezone

from rest_framework import serializers

from records.models import Profile, Record
from records.services import extract_indexed_fields, upsert_known_entities
from records.uischema_injection import inject_schema_defaults, inject_uischema
from records.validators import validate_record

# ---------------------------------------------------------------------------
# fileDetail @type inference from componentType
# ---------------------------------------------------------------------------
# componentType enum values are disjoint across file types, so we can build
# a reverse lookup to infer the correct fileDetail @type from componentType.

# Maps componentType @type prefix → fileDetail @type values
_FILE_TYPE_PREFIXES = {
    # image componentTypes (ada:*Image, ada:*Pattern, ada:ShapeModel*)
    "ada:AIVAImage": ["ada:image", "schema:ImageObject"],
    "ada:LITImage": ["ada:image", "schema:ImageObject"],
    "ada:STEMImage": ["ada:image", "schema:ImageObject"],
    "ada:TEMImage": ["ada:image", "schema:ImageObject"],
    "ada:UVFMImage": ["ada:image", "schema:ImageObject"],
    "ada:VLMImage": ["ada:image", "schema:ImageObject"],
    "ada:XRDDiffractionPattern": ["ada:image", "schema:ImageObject"],
    "ada:ShapeModelImage": ["ada:image", "schema:ImageObject"],
    # imageMap componentTypes
    "ada:basemap": ["ada:imageMap", "schema:ImageObject"],
    "ada:supplementalBasemap": ["ada:imageMap", "schema:ImageObject"],
    # tabularData componentTypes
    "ada:DSCTabular": ["ada:tabularData", "schema:Dataset"],
    "ada:EAIRMSTabular": ["ada:tabularData", "schema:Dataset"],
    "ada:ICPMSTabular": ["ada:tabularData", "schema:Dataset"],
    "ada:XRDTabular": ["ada:tabularData", "schema:Dataset"],
    # dataCube componentTypes
    "ada:VNMIRCube": ["ada:dataCube", "schema:Dataset"],
    "ada:L2MSCube": ["ada:dataCube", "schema:Dataset"],
    # document componentTypes
    "ada:TechnicalReport": ["ada:document", "schema:DigitalDocument"],
    "ada:DataDictionary": ["ada:document", "schema:DigitalDocument"],
    # collection componentTypes
    "ada:SEMImageCollection": ["ada:collection", "https://schema.org/Collection"],
    "ada:TEMEDSImageCollection": ["ada:collection", "https://schema.org/Collection"],
}

# Broad prefix-based fallbacks for componentTypes not explicitly listed
_FILE_TYPE_PREFIX_RULES = [
    ("ada:EMPA", ["ada:imageMap", "schema:ImageObject"]),
    ("ada:SEM", ["ada:imageMap", "schema:ImageObject"]),
    ("ada:NanoSIMS", ["ada:imageMap", "schema:ImageObject"]),
    ("ada:XANES", ["ada:image", "schema:ImageObject"]),
    ("ada:NanoIR", ["ada:imageMap", "schema:ImageObject"]),
    ("ada:VNMIR", ["ada:dataCube", "schema:Dataset"]),
    ("ada:L2MS", ["ada:dataCube", "schema:Dataset"]),
    ("ada:PSFD", ["ada:tabularData", "schema:Dataset"]),
    ("ada:LAF", ["ada:tabularData", "schema:Dataset"]),
]


_CATEGORY_CT_PROPS = [
    "_imageComponentType", "_tabularComponentType",
    "_dataCubeComponentType", "_documentComponentType",
]


def _consolidate_component_type(file_detail):
    """Map per-category UI props back to componentType.@type and strip them."""
    selected = None
    for prop in _CATEGORY_CT_PROPS:
        val = file_detail.pop(prop, None)
        if val and not selected:
            selected = val
    if selected:
        file_detail.setdefault("componentType", {})["@type"] = selected


def _infer_file_detail_type(component_type_value):
    """Infer fileDetail @type from a componentType @type string."""
    if not component_type_value:
        return None
    # Exact match first
    if component_type_value in _FILE_TYPE_PREFIXES:
        return _FILE_TYPE_PREFIXES[component_type_value]
    # Prefix-based fallback
    for prefix, ft in _FILE_TYPE_PREFIX_RULES:
        if component_type_value.startswith(prefix):
            return ft
    return None


def _strip_empty_dict(d):
    """Remove keys whose values are empty strings, empty lists, empty dicts, or None."""
    for key in list(d.keys()):
        v = d[key]
        if v is None or v == "" or v == [] or v == {}:
            del d[key]
        elif isinstance(v, dict):
            _strip_empty_dict(v)
            if not v:
                del d[key]


def _clean_physical_mapping_items(file_detail):
    """Strip UI-only fields and re-wrap formats_InstanceVariable in physicalMapping items."""
    for pm in file_detail.get("cdi:hasPhysicalMapping", []):
        if not isinstance(pm, dict):
            continue
        # Strip _showAdvanced toggle
        pm.pop("_showAdvanced", None)

        # Wrap cdi:formats_InstanceVariable string back to {"@id": "..."}
        fiv = pm.get("cdi:formats_InstanceVariable")
        if isinstance(fiv, str) and fiv:
            pm["cdi:formats_InstanceVariable"] = {"@id": fiv}
        elif isinstance(fiv, str):
            # Empty string — remove the key
            pm.pop("cdi:formats_InstanceVariable", None)


def _relax_type_constraints(schema):
    """Relax overly-restrictive @type enum constraints for validation.

    The OGC Building Block build output produces schemas where @type arrays
    use ``items.enum`` with a single value, preventing dual-typed items.
    For example variableMeasured items need both schema:PropertyValue and
    cdi:InstanceVariable, but the build schema enum only lists one.

    This function converts those single-value ``items.enum`` constraints into
    ``contains`` constraints so the validator only checks that the required
    type is present without rejecting additional types.
    """
    result = copy.deepcopy(schema)

    # variableMeasured items @type
    vm_type = (
        result.get("properties", {})
        .get("schema:variableMeasured", {})
        .get("items", {})
        .get("properties", {})
        .get("@type", {})
    )
    if isinstance(vm_type, dict):
        items_schema = vm_type.get("items", {})
        if isinstance(items_schema, dict) and "enum" in items_schema:
            required = items_schema["enum"][0] if items_schema["enum"] else None
            vm_type["items"] = {"type": "string"}
            if required:
                vm_type["contains"] = {"const": required}
            vm_type.setdefault("minItems", 1)

    # distribution items @type
    dist_items_schema = (
        result.get("properties", {})
        .get("schema:distribution", {})
        .get("items", {})
    )
    dist_type = dist_items_schema.get("properties", {}).get("@type", {})
    if isinstance(dist_type, dict):
        items_schema = dist_type.get("items", {})
        if isinstance(items_schema, dict) and "enum" in items_schema:
            # Allow both DataDownload and WebAPI
            dist_type["items"] = {"type": "string"}
            dist_type.pop("contains", None)  # Don't constrain to one type

    # Strip UI-injected properties from the schema's required lists so
    # stale _distributionType / _showAdvanced don't trip required checks.
    # (additionalProperties is not set, so extra keys are fine.)

    return result


def _jsonld_equal(a: dict, b: dict) -> bool:
    """Compare two JSON-LD documents ignoring volatile auto-populated fields."""
    def _strip_volatile(d):
        d = copy.deepcopy(d)
        d.pop("@id", None)
        so = d.get("schema:subjectOf", {})
        if isinstance(so, dict):
            so.pop("schema:about", None)
            so.pop("schema:sdDatePublished", None)
            so.pop("@id", None)
        d.pop("schema:dateModified", None)
        return d
    return json.dumps(_strip_volatile(a), sort_keys=True) == json.dumps(_strip_volatile(b), sort_keys=True)


def _next_version_identifier(base_identifier: str) -> str:
    """Find next available _N suffix for a base identifier."""
    base = re.sub(r'_\d+$', '', base_identifier)
    existing = Record.objects.filter(identifier__regex=rf'^{re.escape(base)}(_\d+)?$')
    max_ver = 1  # original (no suffix) is implicitly version 1
    for rec in existing:
        m = re.search(r'_(\d+)$', rec.identifier)
        if m:
            max_ver = max(max_ver, int(m.group(1)))
    return f"{base}_{max_ver + 1}"


def _stamp_sd_date_published(jsonld):
    """Set schema:subjectOf.schema:sdDatePublished to the current UTC time."""
    so = jsonld.get("schema:subjectOf")
    if isinstance(so, dict):
        so["schema:sdDatePublished"] = datetime.now(timezone.utc).isoformat()


class ProfileSerializer(serializers.ModelSerializer):
    base_profile = serializers.SlugRelatedField(
        slug_field="name",
        queryset=Profile.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Profile
        fields = [
            "id",
            "name",
            "version",
            "schema",
            "uischema",
            "defaults",
            "description",
            "base_profile",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # Fetch person names for maintainer autocomplete suggestions
        person_names = None
        try:
            from records.models import KnownPerson
            person_names = list(
                KnownPerson.objects.values_list("name", flat=True)
                .distinct()
                .order_by("name")[:100]
            )
        except Exception:
            pass

        if data.get("uischema"):
            data["uischema"] = inject_uischema(data["uischema"], person_names=person_names, profile_name=instance.name)
        if data.get("schema"):
            data["schema"] = inject_schema_defaults(data["schema"], profile_name=instance.name)
        return data


class ProfileListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views (omits large schema fields)."""

    base_profile = serializers.SlugRelatedField(slug_field="name", read_only=True)

    class Meta:
        model = Profile
        fields = [
            "id",
            "name",
            "version",
            "description",
            "base_profile",
            "created_at",
            "updated_at",
        ]


class RecordSerializer(serializers.ModelSerializer):
    profile = serializers.PrimaryKeyRelatedField(queryset=Profile.objects.all())
    profile_name = serializers.CharField(source="profile.name", read_only=True)
    owner_orcid = serializers.CharField(source="owner.orcid", read_only=True, default=None)

    class Meta:
        model = Record
        fields = [
            "id",
            "profile",
            "profile_name",
            "jsonld",
            "title",
            "creators",
            "identifier",
            "status",
            "owner",
            "owner_orcid",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "title",
            "creators",
            "identifier",
            "owner",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        jsonld = attrs.get("jsonld", {})
        profile = attrs.get("profile")

        if not profile:
            # On partial update, use existing profile
            if self.instance:
                profile = self.instance.profile
            else:
                raise serializers.ValidationError({"profile": "This field is required."})

        # Strip UI-only fields before validation and storage
        if jsonld:
            # Clean _showAdvanced from variableMeasured items and ensure @type
            for var in jsonld.get("schema:variableMeasured", []):
                if isinstance(var, dict):
                    var.pop("_showAdvanced", None)
                    # Ensure @type contains both required values
                    vtype = var.get("@type", [])
                    if isinstance(vtype, list):
                        if "schema:PropertyValue" not in vtype:
                            vtype.append("schema:PropertyValue")
                        if "cdi:InstanceVariable" not in vtype:
                            vtype.append("cdi:InstanceVariable")
                        var["@type"] = vtype
                    else:
                        var["@type"] = ["schema:PropertyValue", "cdi:InstanceVariable"]

            # Clean _distributionType from distribution items and set @type
            for dist in jsonld.get("schema:distribution", []):
                if isinstance(dist, dict):
                    dt = dist.pop("_distributionType", None)
                    if dt == "Web API":
                        dist["@type"] = ["schema:WebAPI"]
                    elif dt == "Data Download" or dt is None:
                        dist["@type"] = ["schema:DataDownload"]

                    # Wrap encodingFormat string back to array for JSON-LD storage
                    enc = dist.get("schema:encodingFormat")
                    if isinstance(enc, str) and enc:
                        dist["schema:encodingFormat"] = [enc]
                    elif isinstance(enc, str):
                        dist.pop("schema:encodingFormat", None)

                    # Wrap hasPart encodingFormat strings back to arrays
                    for part in dist.get("schema:hasPart", []):
                        if isinstance(part, dict):
                            hp_enc = part.get("schema:encodingFormat")
                            if isinstance(hp_enc, str) and hp_enc:
                                part["schema:encodingFormat"] = [hp_enc]
                            elif isinstance(hp_enc, str):
                                part.pop("schema:encodingFormat", None)

                    # Clean physicalMapping items in fileDetail
                    fd = dist.get("fileDetail")
                    if isinstance(fd, dict):
                        _consolidate_component_type(fd)
                        _clean_physical_mapping_items(fd)

                        # Infer fileDetail @type from componentType
                        ct = fd.get("componentType")
                        if isinstance(ct, dict):
                            ct_type = ct.get("@type", "")
                            inferred = _infer_file_detail_type(ct_type)
                            if inferred:
                                fd["@type"] = inferred

                        # Strip empty fileDetail to avoid anyOf validation
                        # failures when no componentType has been selected yet
                        if not fd.get("@type") and not fd.get("componentType"):
                            _strip_empty_dict(fd)
                            if not fd:
                                dist.pop("fileDetail", None)

                    # Clean physicalMapping in hasPart fileDetails too
                    for part in dist.get("schema:hasPart", []):
                        if isinstance(part, dict):
                            part_fd = part.get("fileDetail")
                            if isinstance(part_fd, dict):
                                _consolidate_component_type(part_fd)
                                _clean_physical_mapping_items(part_fd)

        # Skip schema validation for draft records (imported data may not
        # conform yet — the user will fix it in the form).
        record_status = attrs.get("status", getattr(self.instance, "status", None))
        if record_status != "draft" and jsonld and profile.schema:
            validation_schema = _relax_type_constraints(profile.schema)
            errors = validate_record(jsonld, validation_schema)
            if errors:
                raise serializers.ValidationError({"jsonld": errors})

        return attrs

    def create(self, validated_data):
        jsonld = validated_data.get("jsonld", {})
        fields = extract_indexed_fields(jsonld)
        user = self.context["request"].user

        validated_data["title"] = fields["title"]
        validated_data["creators"] = fields["creators"]
        validated_data["identifier"] = fields["identifier"] or str(uuid.uuid4())
        validated_data["owner"] = user

        upsert_known_entities(jsonld)

        # Versioning: look up the whole identifier family (base + _N
        # variants) owned by this user.  Compare the newest active
        # version's JSON-LD with the import.
        #   - Identical  → return existing record unchanged.
        #   - Different  → deprecate all active versions, create _N+1.
        # If the identifier is owned by a different user, mint a UUID.
        identifier = validated_data["identifier"]
        existing = Record.objects.filter(identifier=identifier).first()
        if existing:
            if existing.owner_id == user.id:
                base = re.sub(r'_\d+$', '', identifier)
                family = Record.objects.filter(
                    identifier__regex=rf'^{re.escape(base)}(_\d+)?$',
                    owner=user,
                )
                latest = family.exclude(status="deprecated").order_by("-updated_at").first()

                # Same JSON-LD as latest active → reuse, no new version
                if latest and _jsonld_equal(latest.jsonld, jsonld):
                    return latest

                # Different → deprecate all active versions
                family.exclude(status="deprecated").update(status="deprecated")

                new_id = _next_version_identifier(identifier)
                validated_data["identifier"] = new_id

                # Update @id and subjectOf/about in jsonld to match
                jsonld["@id"] = new_id
                if jsonld.get("schema:subjectOf"):
                    jsonld["schema:subjectOf"]["schema:about"] = {"@id": new_id}
            else:
                # Identifier taken by another user — assign a new one
                validated_data["identifier"] = str(uuid.uuid4())

        _stamp_sd_date_published(jsonld)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        jsonld = validated_data.get("jsonld")
        if jsonld:
            fields = extract_indexed_fields(jsonld)
            validated_data["title"] = fields["title"]
            validated_data["creators"] = fields["creators"]
            # Do NOT update identifier on regular save.
            # Identifier changes only happen via the ADA push flow.
            _stamp_sd_date_published(jsonld)
            upsert_known_entities(jsonld)

        return super().update(instance, validated_data)


class RecordListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views (omits full jsonld)."""

    profile_name = serializers.CharField(source="profile.name", read_only=True)
    owner_orcid = serializers.CharField(source="owner.orcid", read_only=True, default=None)
    ada_status = serializers.SerializerMethodField()
    ada_doi = serializers.SerializerMethodField()

    class Meta:
        model = Record
        fields = [
            "id",
            "profile",
            "profile_name",
            "title",
            "creators",
            "identifier",
            "status",
            "owner_orcid",
            "ada_status",
            "ada_doi",
            "created_at",
            "updated_at",
        ]

    def get_ada_status(self, obj):
        try:
            link = obj.ada_link
        except Exception:
            return None
        return link.ada_status or None

    def get_ada_doi(self, obj):
        try:
            link = obj.ada_link
        except Exception:
            return None
        return link.ada_doi or None


class ImportURLSerializer(serializers.Serializer):
    url = serializers.URLField()
    profile = serializers.PrimaryKeyRelatedField(queryset=Profile.objects.all())


class ImportFileSerializer(serializers.Serializer):
    file = serializers.FileField()
    profile = serializers.PrimaryKeyRelatedField(queryset=Profile.objects.all())
