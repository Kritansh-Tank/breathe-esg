from django.db import connection, OperationalError
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .serializers import UserSerializer


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class HealthView(APIView):
    """
    Public health-check endpoint for UptimeRobot monitoring.
    Supports GET and HEAD (HEAD returns headers only, no body — standard HTTP).
    Performs a lightweight DB connectivity check so UptimeRobot catches
    both app crashes AND database outages.
    """
    permission_classes = [AllowAny]

    def _check(self):
        try:
            connection.ensure_connection()
            db_ok = True
        except OperationalError:
            db_ok = False
        return db_ok

    def get(self, request):
        db_ok = self._check()
        payload = {"status": "ok" if db_ok else "degraded", "db": db_ok}
        status_code = 200 if db_ok else 503
        return Response(payload, status=status_code)

    def head(self, request):
        # HEAD must return same status as GET but with no body
        db_ok = self._check()
        return Response(status=200 if db_ok else 503)
