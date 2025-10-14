from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .services import OTPService
from .models import User
from .serializers import (
    UserSerializer,
    # UserProfileSerializer,
    RegistrationSerializer,
    OTPVerificationSerializer,
    LoginSerializer,
    RequestResetSerializer,
    ResetPasswordSerializer,
)
from .throttles import OTPBurstRateThrottle


# -------------------------------
# REGISTRATION VIEW
# -------------------------------
class RegisterView(generics.CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = [AllowAny]
    throttle_classes = [OTPBurstRateThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        result = OTPService.send_otp(user, "activation")
        return Response(result, status=200 if result["success"] else 429)


# -------------------------------
# OTP VERIFICATION VIEW
# -------------------------------
class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({"message": "Account activated successfully"}, status=200)


# -------------------------------
# LOGIN VIEW (JWT-based)
# -------------------------------
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": UserSerializer(user).data,
            }
        )


# -------------------------------
# PASSWORD RESET REQUEST VIEW
# -------------------------------
class RequestResetView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OTPBurstRateThrottle]

    def post(self, request):
        serializer = RequestResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.get(phone=request.data["phone"])
        result = OTPService.send_otp(user, "password_reset")
        return Response(result, status=200 if result["success"] else 429)


# -------------------------------
# PASSWORD RESET CONFIRMATION
# -------------------------------
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({"message": "Password reset successfully"}, status=200)


# -------------------------------
# Resend OTP View
# -------------------------------
class ResendOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OTPBurstRateThrottle]

    def post(self, request):
        phone = request.data.get("phone")
        purpose = request.data.get("purpose", "activation")

        if not phone:
            return Response({"error": "Phone is required."}, status=400)

        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)

        result = OTPService.send_otp(user, purpose)
        status_code = (
            200 if result["success"] else 429
        )  # 429 Too Many Requests if on cooldown
        return Response(result, status=status_code)
