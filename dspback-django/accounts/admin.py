from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("orcid", "first_name", "last_name", "is_staff")
    search_fields = ("orcid", "first_name", "last_name")
    ordering = ("orcid",)
    fieldsets = BaseUserAdmin.fieldsets + (
        ("ORCID", {"fields": ("orcid", "orcid_access_token")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("ORCID", {"fields": ("orcid",)}),
    )
