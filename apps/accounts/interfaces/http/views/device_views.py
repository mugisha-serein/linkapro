# Interface Layer - Device Views (DRF)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..serializers.device_serializer import DeviceSerializer

class DeviceView(APIView):
    def post(self, request):
        serializer = DeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # ...convert to application input, call use case, convert output...
        return Response({'detail': 'Device registered'}, status=status.HTTP_201_CREATED)
