# Interface Layer - Auth Views (DRF)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..serializers.auth.login_serializer import LoginSerializer
from ..serializers.auth.register_serializer import RegisterSerializer

class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # ...convert to application input, call use case, convert output...
        return Response({'detail': 'Login processed'}, status=status.HTTP_200_OK)

class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # ...convert to application input, call use case, convert output...
        return Response({'detail': 'Registration processed'}, status=status.HTTP_201_CREATED)
