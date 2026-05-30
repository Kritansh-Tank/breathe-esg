from django.contrib import admin
from .models import IngestionBatch, RawRecord, NormalizedRecord


@admin.register(IngestionBatch)
class IngestionBatchAdmin(admin.ModelAdmin):
    list_display = ("source_type", "file_name", "row_count", "error_count", "status", "ingested_at", "organization")
    list_filter = ("source_type", "status", "organization")
    readonly_fields = ("id", "ingested_at", "error_log")


@admin.register(RawRecord)
class RawRecordAdmin(admin.ModelAdmin):
    list_display = ("source_row_id", "batch", "parse_error", "created_at")
    list_filter = ("batch__source_type", "organization")
    readonly_fields = ("id", "batch", "organization", "raw_payload", "source_row_id", "parse_error", "created_at")

    def has_change_permission(self, request, obj=None):
        return False  # Raw records are immutable

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(NormalizedRecord)
class NormalizedRecordAdmin(admin.ModelAdmin):
    list_display = ("source_id", "scope", "category", "co2e_kg", "status", "period_start", "organization")
    list_filter = ("scope", "status", "source_type", "category", "organization")
    search_fields = ("source_id", "description", "facility_code")
    readonly_fields = ("id", "raw_record", "batch", "created_at", "updated_at", "emission_factor", "emission_factor_source", "co2e_kg")
