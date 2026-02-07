from django.urls import path

from accounts.views import AuthCallbackView, LoginView, LogoutView

urlpatterns = [
    path("login", LoginView.as_view(), name="login"),
    path("auth", AuthCallbackView.as_view(), name="auth-callback"),
    path("logout", LogoutView.as_view(), name="logout"),
]
