from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Organization, User, AuditLog


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "username", "organization", "role", "is_staff")
    list_filter = ("role", "organization")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Breathe ESG", {"fields": ("organization", "role")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Breathe ESG", {"fields": ("organization", "role")}),
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "target_type", "target_id", "user", "timestamp")
    list_filter = ("action", "target_type", "organization")
    readonly_fields = ("id", "organization", "user", "action", "target_type", "target_id", "diff", "note", "timestamp")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
