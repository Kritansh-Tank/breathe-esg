from rest_framework import serializers
from .models import IngestionBatch, RawRecord, NormalizedRecord


class NormalizedRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = NormalizedRecord
        fields = [
            "id", "source_type", "source_id", "supplier_or_site",
            "scope", "category", "description",
            "activity_quantity", "activity_unit", "activity_unit_original",
            "emission_factor", "emission_factor_source", "co2e_kg",
            "period_start", "period_end", "facility_code", "country",
            "status", "is_edited", "last_edited_by", "last_edited_at",
            "analyst_note", "locked_at", "locked_by",
            "created_at", "updated_at", "batch",
        ]
        read_only_fields = [
            "id", "source_type", "source_id", "scope", "category",
            "emission_factor", "emission_factor_source", "co2e_kg",
            "last_edited_by", "last_edited_at", "locked_at", "locked_by",
            "created_at", "updated_at", "batch",
        ]


class NormalizedRecordEditSerializer(serializers.ModelSerializer):
    """Used for analyst PATCH — only editable fields."""
    class Meta:
        model = NormalizedRecord
        fields = [
            "activity_quantity", "activity_unit",
            "period_start", "period_end",
            "facility_code", "country",
            "description", "supplier_or_site",
            "analyst_note",
        ]


class RawRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRecord
        fields = ["id", "source_row_id", "raw_payload", "parse_error", "created_at"]


class IngestionBatchSerializer(serializers.ModelSerializer):
    record_count = serializers.SerializerMethodField()

    class Meta:
        model = IngestionBatch
        fields = [
            "id", "source_type", "file_name", "ingested_by", "ingested_at",
            "row_count", "error_count", "status", "error_log", "record_count",
        ]
        read_only_fields = fields

    def get_record_count(self, obj):
        return obj.normalized_records.count()


class SummarySerializer(serializers.Serializer):
    scope = serializers.IntegerField()
    category = serializers.CharField()
    co2e_kg_total = serializers.DecimalField(max_digits=18, decimal_places=2)
    record_count = serializers.IntegerField()
