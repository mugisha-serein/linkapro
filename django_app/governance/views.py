from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .serializers import FlagContentSerializer
from .services import get_command_handlers
from application.governance.commands import FlagContentCommand


class FlagContentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FlagContentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cmd = FlagContentCommand(
            reported_by=request.user.id,
            content_type=serializer.validated_data["content_type"],
            content_id=serializer.validated_data["content_id"],
            reason=serializer.validated_data["reason"],
        )

        handlers = get_command_handlers()
        flag_dto = handlers.flag_content(cmd)

        return Response({
            "id": str(flag_dto.id),
            "status": flag_dto.status,
            "message": "Content flagged successfully. Our team will review it."
        }, status=status.HTTP_201_CREATED)