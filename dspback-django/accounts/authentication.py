"""Custom DRF authentication that supports both Bearer header and ?access_token= query param.

Accepts JWTs issued by either dspback (FastAPI, plain jose JWT) or the catalog
backend (Django SimpleJWT). The dspback tokens lack the ``token_type`` claim
that SimpleJWT's ``AccessToken`` class requires, so we decode manually using
PyJWT with the shared signing key.
"""

import jwt
from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication

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

        jwt_settings = settings.SIMPLE_JWT
        signing_key = jwt_settings["SIGNING_KEY"]
        algorithm = jwt_settings.get("ALGORITHM", "HS256")

        try:
            payload = jwt.decode(
                raw_token,
                signing_key,
                algorithms=[algorithm],
            )
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed("Token has expired.")
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed("Invalid token.")

        orcid = payload.get("sub")
        if not orcid:
            raise exceptions.AuthenticationFailed("Token missing 'sub' claim.")

        user, _ = User.objects.get_or_create(
            orcid=orcid,
            defaults={"username": orcid},
        )

        return (user, payload)

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
