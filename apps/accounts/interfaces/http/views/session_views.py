# Interface Layer - Session Views (DRF)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..serializers.session_serializer import SessionSerializer

class SessionView(APIView):
    def post(self, request):
        serializer = SessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # ...convert to application input, call use case, convert output...
        return Response({'detail': 'Session created'}, status=status.HTTP_201_CREATED)

    def delete(self, request):
        # ...parse input, call use case, convert output...
        return Response({'detail': 'Session revoked'}, status=status.HTTP_200_OK)
