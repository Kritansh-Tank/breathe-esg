import uuid
from django.db import models
from core.models import Organization, User


class IngestionBatch(models.Model):
    """
    Represents a single CSV upload event.
    One batch per file upload — groups all RawRecords from that file.
    """
    SOURCE_CHOICES = [
        ("sap", "SAP Fuel & Procurement"),
        ("utility", "Utility Bill (Electricity)"),
        ("travel", "Corporate Travel (Concur)"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("processed", "Processed"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="batches"
    )
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    ingested_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="batches"
    )
    ingested_at = models.DateTimeField(auto_now_add=True)
    file_name = models.CharField(max_length=255)
    row_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_log = models.JSONField(default=list)  # list of {row, error} dicts

    class Meta:
        ordering = ["-ingested_at"]

    def __str__(self):
        return f"{self.source_type} | {self.file_name} | {self.ingested_at:%Y-%m-%d}"


class RawRecord(models.Model):
    """
    Immutable verbatim copy of one row from an uploaded CSV.
    Written once on ingest and never mutated — preserves source-of-truth.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        IngestionBatch, on_delete=models.CASCADE, related_name="raw_records"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="raw_records"
    )
    raw_payload = models.JSONField()        # verbatim CSV row as dict
    source_row_id = models.CharField(max_length=255, blank=True)  # e.g. PO number + item
    parse_error = models.TextField(blank=True)  # if normalization failed
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Raw:{self.batch.source_type}:{self.source_row_id}"


class NormalizedRecord(models.Model):
    """
    Analyst-editable, versioned emission activity record.
    Derived from a RawRecord by the appropriate parser.
    """
    SCOPE_CHOICES = [(1, "Scope 1"), (2, "Scope 2"), (3, "Scope 3")]
    CATEGORY_CHOICES = [
        ("stationary_combustion", "Stationary Combustion (Fuel)"),
        ("mobile_combustion", "Mobile Combustion (Fuel)"),
        ("purchased_electricity", "Purchased Electricity"),
        ("business_travel_air", "Business Travel — Air"),
        ("business_travel_rail", "Business Travel — Rail"),
        ("business_travel_car", "Business Travel — Car/Rental"),
    ]
    STATUS_CHOICES = [
        ("pending_review", "Pending Review"),
        ("approved", "Approved"),
        ("flagged", "Flagged"),
        ("locked", "Locked"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="normalized_records"
    )
    raw_record = models.OneToOneField(
        RawRecord,
        on_delete=models.CASCADE,
        related_name="normalized",
        null=True,
        blank=True,
    )
    batch = models.ForeignKey(
        IngestionBatch, on_delete=models.CASCADE, related_name="normalized_records"
    )

    # ── Source provenance ────────────────────────────────────────────────────
    source_type = models.CharField(max_length=20)          # 'sap' | 'utility' | 'travel'
    source_id = models.CharField(max_length=255, blank=True)  # e.g. PO-1234-10
    supplier_or_site = models.CharField(max_length=255, blank=True)  # vendor / meter / employee

    # ── GHG Classification ───────────────────────────────────────────────────
    scope = models.IntegerField(choices=SCOPE_CHOICES)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.CharField(max_length=500, blank=True)

    # ── Normalized activity ──────────────────────────────────────────────────
    activity_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    activity_unit = models.CharField(max_length=30)  # 'L', 'kWh', 'km', 'passenger_km'
    activity_unit_original = models.CharField(max_length=30, blank=True)  # as-received

    # ── Emission calculation ─────────────────────────────────────────────────
    emission_factor = models.DecimalField(max_digits=18, decimal_places=8)
    emission_factor_source = models.CharField(max_length=100)  # e.g. 'UK_DEFRA_2024'
    co2e_kg = models.DecimalField(max_digits=18, decimal_places=4)  # quantity × factor

    # ── Period + location ────────────────────────────────────────────────────
    period_start = models.DateField()
    period_end = models.DateField()
    facility_code = models.CharField(max_length=100, blank=True)  # plant / meter / cost center
    country = models.CharField(max_length=100, blank=True)

    # ── Review state ─────────────────────────────────────────────────────────
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending_review")
    is_edited = models.BooleanField(default=False)
    last_edited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="edited_records"
    )
    last_edited_at = models.DateTimeField(null=True, blank=True)
    analyst_note = models.TextField(blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="locked_records"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_start"]

    def __str__(self):
        return f"Scope{self.scope} | {self.category} | {self.co2e_kg}kgCO2e | {self.status}"
