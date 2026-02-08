from django.contrib import admin

from records.models import KnownOrganization, KnownPerson, Profile, Record


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "base_profile", "updated_at")
    list_filter = ("base_profile",)
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):
    list_display = ("identifier", "title", "profile", "status", "owner", "updated_at")
    list_filter = ("status", "profile")
    search_fields = ("title", "identifier", "creators")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("owner",)


@admin.register(KnownPerson)
class KnownPersonAdmin(admin.ModelAdmin):
    list_display = ("name", "identifier_type", "identifier_value", "affiliation_name", "last_seen")
    search_fields = ("name", "identifier_value", "affiliation_name")
    readonly_fields = ("last_seen", "created_at")


@admin.register(KnownOrganization)
class KnownOrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "identifier_type", "identifier_value", "last_seen")
    search_fields = ("name", "identifier_value")
    readonly_fields = ("last_seen", "created_at")
