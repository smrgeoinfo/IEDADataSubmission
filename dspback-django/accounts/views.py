"""ORCID OAuth views matching existing frontend expectations.

Flow:
  1. GET /api/login → redirect to ORCID authorize endpoint
  2. GET /api/auth  → ORCID callback, exchange code for token, issue JWT
  3. GET /api/logout → clear session
"""

import requests as http_requests
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.views import View
from rest_framework_simplejwt.tokens import RefreshToken
from urllib.parse import urlencode

from accounts.models import User


class LoginView(View):
    """Redirect to ORCID OAuth authorization."""

    def get(self, request):
        window_close = request.GET.get("window_close", "")
        orcid_cfg = settings.SOCIALACCOUNT_PROVIDERS["orcid"]
        base_domain = orcid_cfg["BASE_DOMAIN"]
        client_id = orcid_cfg["APP"]["client_id"]

        host = settings.OUTSIDE_HOST
        callback_url = f"https://{host}/api/auth"
        if window_close:
            callback_url += f"?window_close={window_close}"

        params = urlencode({
            "client_id": client_id,
            "response_type": "code",
            "scope": "/authenticate",
            "redirect_uri": callback_url,
        })

        return redirect(f"https://{base_domain}/oauth/authorize?{params}")


class AuthCallbackView(View):
    """ORCID OAuth callback — exchange code for ORCID token, then issue JWT."""

    def get(self, request):
        code = request.GET.get("code")
        if not code:
            return JsonResponse({"error": "Missing authorization code"}, status=400)

        window_close = request.GET.get("window_close", "")
        orcid_cfg = settings.SOCIALACCOUNT_PROVIDERS["orcid"]
        base_domain = orcid_cfg["BASE_DOMAIN"]
        client_id = orcid_cfg["APP"]["client_id"]
        client_secret = orcid_cfg["APP"]["secret"]

        host = settings.OUTSIDE_HOST
        callback_url = f"https://{host}/api/auth"
        if window_close:
            callback_url += f"?window_close={window_close}"

        # Exchange code for ORCID access token
        token_resp = http_requests.post(
            f"https://{base_domain}/oauth/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": callback_url,
            },
            headers={"Accept": "application/json"},
            timeout=30,
        )

        if token_resp.status_code != 200:
            return JsonResponse(
                {"error": "Failed to exchange code", "detail": token_resp.text},
                status=502,
            )

        token_data = token_resp.json()
        orcid_id = token_data.get("orcid")
        access_token = token_data.get("access_token")

        if not orcid_id:
            return JsonResponse({"error": "ORCID not in token response"}, status=502)

        # Get or create local user
        user, _created = User.objects.get_or_create(
            orcid=orcid_id,
            defaults={
                "username": orcid_id,
                "orcid_access_token": access_token,
            },
        )
        if not _created and access_token:
            user.orcid_access_token = access_token
            user.save(update_fields=["orcid_access_token"])

        # Populate name from ORCID response if available
        name = token_data.get("name", "")
        if name and not user.first_name:
            parts = name.split(" ", 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ""
            user.save(update_fields=["first_name", "last_name"])

        # Issue JWT
        refresh = RefreshToken.for_user(user)
        jwt_access = str(refresh.access_token)
        jwt_refresh = str(refresh)

        # If window_close, return HTML that posts message to opener
        if window_close:
            html = f"""<!DOCTYPE html>
<html><body><script>
window.opener.postMessage({{
    access_token: "{jwt_access}",
    token_type: "Bearer"
}}, "*");
window.close();
</script></body></html>"""
            return HttpResponse(html, content_type="text/html")

        return JsonResponse({
            "access_token": jwt_access,
            "refresh_token": jwt_refresh,
            "token_type": "Bearer",
            "orcid": orcid_id,
        })


class LogoutView(View):
    """Clear session."""

    def get(self, request):
        request.session.flush()
        return JsonResponse({"status": "logged out"})
