from django.contrib import admin

from ada_bridge.models import AdaRecordLink, BundleSession


@admin.register(AdaRecordLink)
class AdaRecordLinkAdmin(admin.ModelAdmin):
    list_display = [
        "ieda_record",
        "ada_record_id",
        "ada_status",
        "ada_doi",
        "last_pushed_at",
        "last_synced_at",
    ]
    list_filter = ["ada_status"]
    search_fields = ["ada_doi", "ada_record_id"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(BundleSession)
class BundleSessionAdmin(admin.ModelAdmin):
    list_display = [
        "session_id",
        "user",
        "status",
        "profile_id",
        "created_at",
        "updated_at",
    ]
    list_filter = ["status"]
    search_fields = ["session_id"]
    readonly_fields = ["session_id", "created_at", "updated_at"]
