import json
import logging
import uuid

import requests as http_requests
from django.conf import settings
from django.http import JsonResponse
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from records.models import KnownOrganization, KnownPerson, Profile, Record
from records.serializers import (
    ImportFileSerializer,
    ImportURLSerializer,
    ProfileListSerializer,
    ProfileSerializer,
    RecordListSerializer,
    RecordSerializer,
)
from records.services import extract_indexed_fields, fetch_jsonld_from_url, upsert_known_entities
from records.profile_detection import detect_profile
from records.validators import validate_record

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def me_view(request):
    """Return authenticated user's profile info (name, ORCID).

    If first_name is missing, attempt to fetch from ORCID public API and cache it.
    """
    user = request.user

    # If we don't have the user's name yet, fetch from ORCID public API
    if not user.first_name and user.orcid:
        try:
            orcid_cfg = settings.SOCIALACCOUNT_PROVIDERS.get("orcid", {})
            base_domain = orcid_cfg.get("BASE_DOMAIN", "orcid.org")
            # Use pub API (no auth required)
            resp = http_requests.get(
                f"https://pub.{base_domain}/v3.0/{user.orcid}/person",
                headers={"Accept": "application/json"},
                timeout=10,
            )
            if resp.status_code == 200:
                person = resp.json()
                given = person.get("name", {}).get("given-names", {}).get("value", "")
                family = person.get("name", {}).get("family-name", {}).get("value", "")
                if given or family:
                    user.first_name = given
                    user.last_name = family
                    user.save(update_fields=["first_name", "last_name"])
        except Exception:
            logger.warning("Failed to fetch ORCID profile for %s", user.orcid)

    name = f"{user.first_name} {user.last_name}".strip()
    return Response({
        "orcid": user.orcid,
        "name": name,
        "first_name": user.first_name,
        "last_name": user.last_name,
    })


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Allow write access only to the record owner."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner == request.user


class ProfileViewSet(viewsets.ModelViewSet):
    """CRUD for metadata profiles. Public read, admin write."""

    queryset = Profile.objects.all()
    lookup_field = "name"
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return ProfileListSerializer
        return ProfileSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]


class RecordViewSet(viewsets.ModelViewSet):
    """CRUD for JSON-LD metadata records."""

    queryset = Record.objects.select_related("profile", "owner").prefetch_related("ada_link").all()
    search_fields = ["title", "identifier", "creators"]
    ordering_fields = ["title", "created_at", "updated_at", "status"]
    filterset_fields = ["profile", "status"]

    def get_serializer_class(self):
        if self.action == "list":
            return RecordListSerializer
        return RecordSerializer

    def get_permissions(self):
        if self.action in ("create", "import_url", "import_file"):
            return [permissions.IsAuthenticated()]
        if self.action in ("update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsOwnerOrReadOnly()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()

        # Filter to current user's records when ?mine=true
        if self.request.query_params.get("mine") == "true" and self.request.user.is_authenticated:
            qs = qs.filter(owner=self.request.user)

        # Filter by profile name
        profile_name = self.request.query_params.get("profile")
        if profile_name:
            qs = qs.filter(profile__name=profile_name)

        # Filter by status
        record_status = self.request.query_params.get("status")
        if record_status:
            qs = qs.filter(status=record_status)

        # Exclude by status (e.g., ?exclude_status=deprecated)
        exclude_status = self.request.query_params.get("exclude_status")
        if exclude_status:
            qs = qs.exclude(status=exclude_status)

        return qs

    @action(detail=True, methods=["get"], url_path="jsonld")
    def jsonld(self, request, pk=None):
        """Return raw JSON-LD with application/ld+json content type."""
        record = self.get_object()
        return JsonResponse(record.jsonld, content_type="application/ld+json")

    @action(detail=False, methods=["post"], url_path="import-url")
    def import_url(self, request):
        """Import a record from a URL pointing to a JSON-LD document."""
        serializer = ImportURLSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        url = serializer.validated_data["url"]
        profile = serializer.validated_data["profile"]

        try:
            jsonld = fetch_jsonld_from_url(url)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Validate against profile schema
        if profile.schema:
            from records.serializers import _relax_type_constraints
            validation_schema = _relax_type_constraints(profile.schema)
            errors = validate_record(jsonld, validation_schema)
            if errors:
                return Response(
                    {"jsonld": errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        fields = extract_indexed_fields(jsonld)
        upsert_known_entities(jsonld)
        record = Record.objects.create(
            profile=profile,
            jsonld=jsonld,
            title=fields["title"],
            creators=fields["creators"],
            identifier=fields["identifier"] or str(uuid.uuid4()),
            owner=request.user,
        )

        return Response(
            RecordSerializer(record, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="import-file")
    def import_file(self, request):
        """Import a record from an uploaded JSON-LD file."""
        serializer = ImportFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded = serializer.validated_data["file"]
        profile = serializer.validated_data["profile"]

        try:
            content = uploaded.read().decode("utf-8")
            jsonld = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return Response(
                {"error": f"Invalid JSON file: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate against profile schema
        if profile.schema:
            from records.serializers import _relax_type_constraints
            validation_schema = _relax_type_constraints(profile.schema)
            errors = validate_record(jsonld, validation_schema)
            if errors:
                return Response(
                    {"jsonld": errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        fields = extract_indexed_fields(jsonld)
        upsert_known_entities(jsonld)
        record = Record.objects.create(
            profile=profile,
            jsonld=jsonld,
            title=fields["title"],
            creators=fields["creators"],
            identifier=fields["identifier"] or str(uuid.uuid4()),
            owner=request.user,
        )

        return Response(
            RecordSerializer(record, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def persons_search(request):
    """Search known persons by name for autocomplete pick lists."""
    q = request.query_params.get("q", "").strip()
    qs = KnownPerson.objects.all()
    if q:
        qs = qs.filter(name__icontains=q)
    qs = qs.order_by("-last_seen")[:50]

    results = []
    for person in qs:
        item = {"schema:name": person.name}
        if person.identifier_value:
            item["schema:identifier"] = {
                "@type": "schema:PropertyValue",
                "schema:propertyID": person.identifier_type,
                "schema:value": person.identifier_value,
                "schema:url": person.identifier_url,
            }
        if person.affiliation_name:
            affil = {
                "@type": "schema:Organization",
                "schema:name": person.affiliation_name,
            }
            if person.affiliation_identifier_value:
                affil["schema:identifier"] = {
                    "@type": "schema:PropertyValue",
                    "schema:propertyID": person.affiliation_identifier_type,
                    "schema:value": person.affiliation_identifier_value,
                    "schema:url": person.affiliation_identifier_url,
                }
            item["schema:affiliation"] = affil
        results.append(item)

    return Response({"results": results})


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def organizations_search(request):
    """Search known organizations by name for autocomplete pick lists."""
    q = request.query_params.get("q", "").strip()
    qs = KnownOrganization.objects.all()
    if q:
        qs = qs.filter(name__icontains=q)
    qs = qs.order_by("-last_seen")[:50]

    results = []
    for org in qs:
        item = {"schema:name": org.name}
        if org.identifier_value:
            item["schema:identifier"] = {
                "@type": "schema:PropertyValue",
                "schema:propertyID": org.identifier_type,
                "schema:value": org.identifier_value,
                "schema:url": org.identifier_url,
            }
        results.append(item)

    return Response({"results": results})


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def detect_profile_view(request):
    """Detect the best-matching profile from JSON-LD content."""
    jsonld = request.data.get("jsonld")
    if not jsonld or not isinstance(jsonld, dict):
        return Response({"detail": "jsonld field required"}, status=status.HTTP_400_BAD_REQUEST)
    result = detect_profile(jsonld)
    # Verify detected profile exists in DB
    if result["profile"]:
        if not Profile.objects.filter(name=result["profile"]).exists():
            result = {"profile": None, "source": None}
    return Response(result)
