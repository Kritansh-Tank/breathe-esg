import io
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Count
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import AuditLog
from .models import IngestionBatch, RawRecord, NormalizedRecord
from .serializers import (
    IngestionBatchSerializer,
    NormalizedRecordSerializer,
    NormalizedRecordEditSerializer,
)
from .parsers.sap_parser import parse_sap_csv
from .parsers.utility_parser import parse_utility_csv
from .parsers.travel_parser import parse_travel_csv


PARSER_MAP = {
    "sap": parse_sap_csv,
    "utility": parse_utility_csv,
    "travel": parse_travel_csv,
}


class StandardPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200


# ── Upload endpoint ────────────────────────────────────────────────────────────

class UploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role not in ("analyst", "admin"):
            return Response({"error": "Only analysts and admins can upload data."}, status=403)

        source_type = request.data.get("source_type", "").lower()
        if source_type not in PARSER_MAP:
            return Response(
                {"error": f"source_type must be one of: {list(PARSER_MAP.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            content = uploaded_file.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                uploaded_file.seek(0)
                content = uploaded_file.read().decode("latin-1")
            except Exception as e:
                return Response({"error": f"Cannot decode file: {e}"}, status=400)

        org = request.user.organization
        if org is None:
            return Response({"error": "User has no organization."}, status=403)

        with transaction.atomic():
            batch = IngestionBatch.objects.create(
                organization=org,
                source_type=source_type,
                ingested_by=request.user,
                file_name=uploaded_file.name,
                status="processing",
            )

            parser = PARSER_MAP[source_type]
            results = parser(content, batch.id, org.id)

            ok_count = 0
            err_count = 0
            error_log = []

            for result in results:
                raw = RawRecord.objects.create(
                    batch=batch,
                    organization=org,
                    raw_payload=result["raw_payload"],
                    source_row_id=result["source_row_id"],
                    parse_error=result["parse_error"],
                )

                if result["parse_error"]:
                    err_count += 1
                    error_log.append({
                        "row": result["source_row_id"] or "?",
                        "error": result["parse_error"],
                    })
                    continue

                norm_data = result["normalized"]
                NormalizedRecord.objects.create(
                    organization=org,
                    raw_record=raw,
                    batch=batch,
                    **norm_data,
                )
                ok_count += 1

            batch.row_count = ok_count
            batch.error_count = err_count
            batch.error_log = error_log
            batch.status = "processed" if err_count == 0 else (
                "failed" if ok_count == 0 else "processed"
            )
            batch.save()

            AuditLog.objects.create(
                organization=org,
                user=request.user,
                action="ingest",
                target_type="IngestionBatch",
                target_id=str(batch.id),
                diff={},
                note=f"Ingested {ok_count} records, {err_count} errors from {uploaded_file.name}",
            )

        return Response(IngestionBatchSerializer(batch).data, status=status.HTTP_201_CREATED)


# ── Batch list ─────────────────────────────────────────────────────────────────

class BatchListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = request.user.organization
        qs = IngestionBatch.objects.filter(organization=org)
        source_type = request.query_params.get("source_type")
        if source_type:
            qs = qs.filter(source_type=source_type)
        serializer = IngestionBatchSerializer(qs, many=True)
        return Response(serializer.data)


# ── Normalized records list + detail ──────────────────────────────────────────

class NormalizedRecordListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = request.user.organization
        qs = NormalizedRecord.objects.filter(organization=org).select_related(
            "last_edited_by", "locked_by", "batch"
        )

        for field in ("scope", "status", "source_type", "category", "facility_code", "country"):
            val = request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})

        batch_id = request.query_params.get("batch_id")
        if batch_id:
            qs = qs.filter(batch_id=batch_id)

        period_from = request.query_params.get("period_from")
        period_to = request.query_params.get("period_to")
        if period_from:
            qs = qs.filter(period_start__gte=period_from)
        if period_to:
            qs = qs.filter(period_end__lte=period_to)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(NormalizedRecordSerializer(page, many=True).data)


class NormalizedRecordDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_record(self, pk, org):
        try:
            return NormalizedRecord.objects.get(pk=pk, organization=org)
        except NormalizedRecord.DoesNotExist:
            return None

    def get(self, request, pk):
        record = self._get_record(pk, request.user.organization)
        if not record:
            return Response({"error": "Not found."}, status=404)
        return Response(NormalizedRecordSerializer(record).data)

    def patch(self, request, pk):
        if request.user.role not in ("analyst", "admin"):
            return Response({"error": "Only analysts and admins can edit records."}, status=403)

        record = self._get_record(pk, request.user.organization)
        if not record:
            return Response({"error": "Not found."}, status=404)
        if record.status == "locked":
            return Response({"error": "Record is locked and cannot be edited."}, status=403)

        before = NormalizedRecordSerializer(record).data
        serializer = NormalizedRecordEditSerializer(record, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        record = serializer.save(
            is_edited=True,
            last_edited_by=request.user,
            last_edited_at=timezone.now(),
        )

        after = NormalizedRecordSerializer(record).data
        AuditLog.objects.create(
            organization=request.user.organization,
            user=request.user,
            action="edit",
            target_type="NormalizedRecord",
            target_id=str(record.id),
            diff={"before": before, "after": after},
        )
        return Response(NormalizedRecordSerializer(record).data)


# ── Review actions ─────────────────────────────────────────────────────────────

class ApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ("analyst", "admin"):
            return Response({"error": "Only analysts and admins can approve records."}, status=403)

        try:
            record = NormalizedRecord.objects.get(pk=pk, organization=request.user.organization)
        except NormalizedRecord.DoesNotExist:
            return Response({"error": "Not found."}, status=404)

        if record.status == "locked":
            return Response({"error": "Cannot approve a locked record."}, status=403)

        if record.status == "approved":
            return Response({"error": "Record is already approved."}, status=400)

        record.status = "approved"
        record.save(update_fields=["status", "updated_at"])

        AuditLog.objects.create(
            organization=request.user.organization,
            user=request.user,
            action="approve",
            target_type="NormalizedRecord",
            target_id=str(record.id),
            diff={},
        )
        return Response({"status": "approved"})


class FlagView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ("analyst", "admin"):
            return Response({"error": "Only analysts and admins can flag records."}, status=403)

        try:
            record = NormalizedRecord.objects.get(pk=pk, organization=request.user.organization)
        except NormalizedRecord.DoesNotExist:
            return Response({"error": "Not found."}, status=404)

        if record.status == "locked":
            return Response({"error": "Cannot flag a locked record."}, status=403)

        note = request.data.get("note", "")
        record.status = "flagged"
        record.analyst_note = note
        record.save(update_fields=["status", "analyst_note", "updated_at"])

        AuditLog.objects.create(
            organization=request.user.organization,
            user=request.user,
            action="flag",
            target_type="NormalizedRecord",
            target_id=str(record.id),
            note=note,
            diff={},
        )
        return Response({"status": "flagged"})


class LockView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role != "admin":
            return Response({"error": "Only admins can lock records."}, status=403)

        try:
            record = NormalizedRecord.objects.get(pk=pk, organization=request.user.organization)
        except NormalizedRecord.DoesNotExist:
            return Response({"error": "Not found."}, status=404)

        if record.status != "approved":
            return Response({"error": "Only approved records can be locked."}, status=400)

        record.status = "locked"
        record.locked_at = timezone.now()
        record.locked_by = request.user
        record.save(update_fields=["status", "locked_at", "locked_by", "updated_at"])

        AuditLog.objects.create(
            organization=request.user.organization,
            user=request.user,
            action="lock",
            target_type="NormalizedRecord",
            target_id=str(record.id),
            diff={},
        )
        return Response({"status": "locked"})


class BulkApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role not in ("analyst", "admin"):
            return Response({"error": "Only analysts and admins can approve records."}, status=403)

        ids = request.data.get("ids", [])
        if not ids:
            return Response({"error": "No IDs provided."}, status=400)

        org = request.user.organization
        qs = NormalizedRecord.objects.filter(
            id__in=ids, organization=org
        ).exclude(status="locked")

        updated = qs.update(status="approved")

        for record_id in ids:
            AuditLog.objects.create(
                organization=org,
                user=request.user,
                action="approve",
                target_type="NormalizedRecord",
                target_id=str(record_id),
                diff={},
                note=f"bulk approve ({updated} records)" if updated > 1 else "approved",
            )

        return Response({"approved": updated})


# ── Summary ────────────────────────────────────────────────────────────────────

class SummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = request.user.organization
        qs = NormalizedRecord.objects.filter(organization=org)

        period_from = request.query_params.get("period_from")
        period_to = request.query_params.get("period_to")
        if period_from:
            qs = qs.filter(period_start__gte=period_from)
        if period_to:
            qs = qs.filter(period_end__lte=period_to)

        by_scope = (
            qs.values("scope")
            .annotate(co2e_kg_total=Sum("co2e_kg"), record_count=Count("id"))
            .order_by("scope")
        )

        by_category = (
            qs.values("scope", "category")
            .annotate(co2e_kg_total=Sum("co2e_kg"), record_count=Count("id"))
            .order_by("scope", "category")
        )

        by_status = (
            qs.values("status")
            .annotate(count=Count("id"))
        )

        totals = qs.aggregate(total_co2e=Sum("co2e_kg"), total_records=Count("id"))

        return Response({
            "total_co2e_kg": totals["total_co2e"] or 0,
            "total_co2e_tonne": float(totals["total_co2e"] or 0) / 1000,
            "total_records": totals["total_records"],
            "by_scope": list(by_scope),
            "by_category": list(by_category),
            "by_status": list(by_status),
        })


# ── Audit log ─────────────────────────────────────────────────────────────────

class AuditLogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from core.serializers import AuditLogSerializer
        org = request.user.organization
        qs = AuditLog.objects.filter(organization=org)

        target_type = request.query_params.get("target_type")
        if target_type:
            qs = qs.filter(target_type=target_type)
        action = request.query_params.get("action")
        if action:
            qs = qs.filter(action=action)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(AuditLogSerializer(page, many=True).data)
