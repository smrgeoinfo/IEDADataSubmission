from django.contrib import admin

from records.models import Profile, Record


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
