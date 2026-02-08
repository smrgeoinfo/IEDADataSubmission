import uuid

from rest_framework import serializers

from records.models import Profile, Record
from records.services import extract_indexed_fields, upsert_known_entities
from records.uischema_injection import inject_schema_defaults, inject_uischema
from records.validators import validate_record


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
        if data.get("uischema"):
            data["uischema"] = inject_uischema(data["uischema"])
        if data.get("schema"):
            data["schema"] = inject_schema_defaults(data["schema"])
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
