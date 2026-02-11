from django.contrib import admin

from ada_bridge.models import AdaRecordLink


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
