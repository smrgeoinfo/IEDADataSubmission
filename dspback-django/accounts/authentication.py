"""Custom DRF authentication that supports both Bearer header and ?access_token= query param."""

from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User


class JWTAuthentication(BaseAuthentication):
    """Authenticate via JWT from Authorization header or access_token query param.

    Supports:
      - Authorization: Bearer <token>
      - ?access_token=<token>
    """

    def authenticate(self, request):
        raw_token = self._get_raw_token(request)
        if raw_token is None:
            return None

        try:
            validated = AccessToken(raw_token)
        except Exception:
            raise exceptions.AuthenticationFailed("Invalid or expired token.")

        orcid = validated.get("sub")
        if not orcid:
            raise exceptions.AuthenticationFailed("Token missing 'sub' claim.")

        user, _ = User.objects.get_or_create(
            orcid=orcid,
            defaults={"username": orcid},
        )

        return (user, validated)

    def _get_raw_token(self, request):
        # Check Authorization header first
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if header.startswith("Bearer "):
            return header[7:]

        # Fall back to query param (for frontend compatibility)
        token = request.query_params.get("access_token")
        if token:
            return token

        return None
