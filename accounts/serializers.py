from rest_framework import serializers
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import User, OTPVerification, ShippingAddress, iraq_phone_validator
from .services import OTPService


def normalize_and_validate_phone(value: str) -> str:
    phone = str(value).strip()
    try:
        iraq_phone_validator(phone)
    except DjangoValidationError as exc:
        # surface the first message from the validator
        message = exc.messages[0] if hasattr(exc, "messages") else "Invalid phone number."
        raise serializers.ValidationError(message)
    return phone


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
        read_only_fields = ["user"]


# -------------------------------
# REGISTRATION SERIALIZER
# -------------------------------
class RegistrationSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    password = serializers.CharField(write_only=True)

    def validate_phone(self, value):
        phone = normalize_and_validate_phone(value)
        if User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError("A user with this phone already exists.")
        return phone

    def create(self, validated_data):
        phone = normalize_and_validate_phone(validated_data["phone"])
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
        phone = normalize_and_validate_phone(attrs["phone"])
        otp = attrs["otp"]
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")

        result = OTPService.verify_with_attempt_limit(
            user=user, purpose="activation", code=otp
        )
        if not result["success"]:
            raise serializers.ValidationError(result["message"])

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
        phone = normalize_and_validate_phone(attrs.get("phone"))
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
        phone = normalize_and_validate_phone(attrs["phone"])
        try:
            user = User.objects.get(phone=phone, role="customer")
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "No active customer with this phone number"
            )
        attrs["phone"] = phone
        return attrs


class ResetPasswordSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        phone = normalize_and_validate_phone(attrs["phone"])
        otp = attrs["otp"]
        new_password = attrs["new_password"]

        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")

        result = OTPService.verify_with_attempt_limit(
            user=user, purpose="password_reset", code=otp
        )
        if not result["success"]:
            raise serializers.ValidationError(result["message"])

        user.set_password(new_password)
        user.save()
        attrs["phone"] = phone
        return attrs
