from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, OTPVerification, ShippingAddress


# -------------------------------
# USER  SERIALIZER
# -------------------------------
class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "role",
            "is_active",
        ]
        read_only_fields = ["is_active", "role"]

    def create(self, validated_data):

        user = User.objects.create_user(**validated_data)
        if user.role == "customer":
            # Customer starts inactive until OTP verification
            user.is_active = False
            user.save()

        return user


# -------------------------------
# USER SHIPPING ADDRESS SERIALIZER
# -------------------------------
class ShippingAdressSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = ShippingAddress
        fields = [
            "user",
            "city",
            "city_id",
            "region",
            "region_id",
            "location",
            "client_mobile2",
        ]


# -------------------------------
# REGISTRATION SERIALIZER
# -------------------------------
class RegistrationSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    password = serializers.CharField(write_only=True)

    def create(self, validated_data):
        phone = validated_data["phone"]
        password = validated_data["password"]
        user = User.objects.create_user(
            phone=phone, password=password, role="customer", is_active=False
        )
        # OTPVerification.create_otp(user, purpose="activation")
        return user


# -------------------------------
# OTP VERIFICATION SERIALIZER
# -------------------------------
class OTPVerificationSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)

    def validate(self, attrs):
        phone = attrs["phone"]
        otp = attrs["otp"]
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")

        otp_entry = OTPVerification.objects.filter(
            user=user, purpose="activation", is_used=False
        ).last()
        if not otp_entry or not otp_entry.verify(otp):
            raise serializers.ValidationError("Invalid or expired OTP")

        # Activate the user
        user.is_active = True
        user.save()
        return attrs


# -------------------------------
# LOGIN SERIALIZER
# -------------------------------
class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        phone = attrs.get("phone")
        password = attrs.get("password")
        user = authenticate(phone=phone, password=password)
        if not user:
            raise serializers.ValidationError("Invalid credentials or inactive account")
        attrs["user"] = user
        return attrs


# -------------------------------
# PASSWORD RESET SERIALIZERS
# -------------------------------
class RequestResetSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)

    def validate(self, attrs):
        phone = attrs["phone"]
        try:
            user = User.objects.get(phone=phone, role="customer")
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "No active customer with this phone number"
            )
        OTPVerification.create_otp(user, purpose="password_reset")
        return attrs


class ResetPasswordSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        phone = attrs["phone"]
        otp = attrs["otp"]
        new_password = attrs["new_password"]

        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")

        otp_entry = OTPVerification.objects.filter(
            user=user, purpose="password_reset", is_used=False
        ).last()
        if not otp_entry or not otp_entry.verify(otp):
            raise serializers.ValidationError("Invalid or expired OTP")

        user.set_password(new_password)
        user.save()
        return attrs
