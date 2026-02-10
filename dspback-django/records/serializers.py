import uuid

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
            data["uischema"] = inject_uischema(data["uischema"], person_names=person_names)
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
            # Clean _showAdvanced from variableMeasured items
            for var in jsonld.get("schema:variableMeasured", []):
                if isinstance(var, dict):
                    var.pop("_showAdvanced", None)

            # Clean _distributionType from distribution items and set @type
            for dist in jsonld.get("schema:distribution", []):
                if isinstance(dist, dict):
                    dt = dist.pop("_distributionType", None)
                    if dt == "Web API":
                        dist["@type"] = ["schema:WebAPI"]
                    elif dt == "Data Download" or dt is None:
                        dist.setdefault("@type", ["schema:DataDownload"])

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
                        _clean_physical_mapping_items(fd)

                        # Infer fileDetail @type from componentType
                        ct = fd.get("componentType")
                        if isinstance(ct, dict):
                            ct_type = ct.get("@type", "")
                            inferred = _infer_file_detail_type(ct_type)
                            if inferred:
                                fd["@type"] = inferred

                    # Clean physicalMapping in hasPart fileDetails too
                    for part in dist.get("schema:hasPart", []):
                        if isinstance(part, dict):
                            part_fd = part.get("fileDetail")
                            if isinstance(part_fd, dict):
                                _clean_physical_mapping_items(part_fd)

        if jsonld and profile.schema:
            errors = validate_record(jsonld, profile.schema)
            if errors:
                raise serializers.ValidationError({"jsonld": errors})

        return attrs

    def create(self, validated_data):
        jsonld = validated_data.get("jsonld", {})
        fields = extract_indexed_fields(jsonld)

        validated_data["title"] = fields["title"]
        validated_data["creators"] = fields["creators"]
        validated_data["identifier"] = fields["identifier"] or str(uuid.uuid4())
        validated_data["owner"] = self.context["request"].user

        upsert_known_entities(jsonld)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        jsonld = validated_data.get("jsonld")
        if jsonld:
            fields = extract_indexed_fields(jsonld)
            validated_data["title"] = fields["title"]
            validated_data["creators"] = fields["creators"]
            if fields["identifier"]:
                validated_data["identifier"] = fields["identifier"]
            upsert_known_entities(jsonld)

        return super().update(instance, validated_data)


class RecordListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views (omits full jsonld)."""

    profile_name = serializers.CharField(source="profile.name", read_only=True)
    owner_orcid = serializers.CharField(source="owner.orcid", read_only=True, default=None)

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
            "created_at",
            "updated_at",
        ]


class ImportURLSerializer(serializers.Serializer):
    url = serializers.URLField()
    profile = serializers.PrimaryKeyRelatedField(queryset=Profile.objects.all())


class ImportFileSerializer(serializers.Serializer):
    file = serializers.FileField()
    profile = serializers.PrimaryKeyRelatedField(queryset=Profile.objects.all())
