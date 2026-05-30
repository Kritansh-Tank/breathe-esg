import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class Organization(models.Model):
    """Tenant. Every data object is scoped to an organization."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("analyst", "Analyst"),
        ("auditor", "Auditor"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="analyst")

    def __str__(self):
        return f"{self.email} ({self.organization})"


class AuditLog(models.Model):
    """
    Immutable append-only audit trail.
    Written by signal handlers and explicit service calls — never updated or deleted.
    """
    ACTION_CHOICES = [
        ("ingest", "Ingest"),
        ("edit", "Edit"),
        ("approve", "Approve"),
        ("flag", "Flag"),
        ("lock", "Lock"),
        ("unlock", "Unlock"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="audit_logs"
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="audit_logs"
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=50)   # e.g. 'NormalizedRecord'
    target_id = models.CharField(max_length=100)     # UUID as string
    diff = models.JSONField(default=dict)            # {before: {...}, after: {...}}
    note = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action} on {self.target_type}:{self.target_id} by {self.user}"
