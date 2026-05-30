"""
Management command: seed_data
Creates demo organization, users, and sample ingestion batches
with realistic data for the three source types.

Run: python manage.py seed_data
"""

import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Organization

User = get_user_model()


class Command(BaseCommand):
    help = "Seed demo data for the Breathe ESG platform"

    def handle(self, *args, **kwargs):
        # ── Organization ──────────────────────────────────────────────────────
        org, created = Organization.objects.get_or_create(
            slug="acme-corp",
            defaults={"name": "Acme Corporation"},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created org: {org.name}"))
        else:
            self.stdout.write(f"Org exists: {org.name}")

        # ── Users ─────────────────────────────────────────────────────────────
        users_to_create = [
            {
                "username": "admin@acme.com",
                "email": "admin@acme.com",
                "first_name": "Sarah",
                "last_name": "Chen",
                "role": "admin",
                "password": "breathe123",
                "is_staff": True,
            },
            {
                "username": "analyst@acme.com",
                "email": "analyst@acme.com",
                "first_name": "James",
                "last_name": "Okafor",
                "role": "analyst",
                "password": "breathe123",
            },
            {
                "username": "auditor@acme.com",
                "email": "auditor@acme.com",
                "first_name": "Priya",
                "last_name": "Sharma",
                "role": "auditor",
                "password": "breathe123",
            },
        ]

        for u_data in users_to_create:
            password = u_data.pop("password")
            is_staff = u_data.pop("is_staff", False)
            user, created = User.objects.get_or_create(
                username=u_data["username"],
                defaults={**u_data, "organization": org, "is_staff": is_staff},
            )
            if created:
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Created user: {user.email} ({user.role})"))
            else:
                self.stdout.write(f"User exists: {user.email}")

        self.stdout.write(self.style.SUCCESS("\nSeed complete! Login credentials:"))
        self.stdout.write("  admin@acme.com / breathe123  (admin)")
        self.stdout.write("  analyst@acme.com / breathe123  (analyst)")
        self.stdout.write("  auditor@acme.com / breathe123  (auditor)")
        self.stdout.write("\nUpload sample CSVs from the /sample_data/ directory via the UI.")
