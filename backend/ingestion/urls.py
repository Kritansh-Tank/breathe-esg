from django.urls import path
from . import views

urlpatterns = [
    # Upload
    path("upload/", views.UploadView.as_view(), name="upload"),
    # Batches
    path("batches/", views.BatchListView.as_view(), name="batch-list"),
    # Normalized records
    path("records/", views.NormalizedRecordListView.as_view(), name="record-list"),
    path("records/summary/", views.SummaryView.as_view(), name="record-summary"),
    path("records/bulk-approve/", views.BulkApproveView.as_view(), name="record-bulk-approve"),
    path("records/<uuid:pk>/", views.NormalizedRecordDetailView.as_view(), name="record-detail"),
    path("records/<uuid:pk>/approve/", views.ApproveView.as_view(), name="record-approve"),
    path("records/<uuid:pk>/flag/", views.FlagView.as_view(), name="record-flag"),
    path("records/<uuid:pk>/lock/", views.LockView.as_view(), name="record-lock"),
    # Audit log
    path("audit-log/", views.AuditLogView.as_view(), name="audit-log"),
]
