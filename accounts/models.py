from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.utils import timezone
import random
from datetime import timedelta
from .utils import send_whatsapp_message
from django.core.validators import RegexValidator


iraq_phone_validator = RegexValidator(
    regex=r"^(?:\+964|00964|0)?7(7|8|9|5)\d{8}$",
    message="أدخل رقم هاتف عراقي صحيح (مثال: 07801234567 أو +9647801234567).",
)


# ----------------------------------------
# USER MANAGER
# ----------------------------------------
class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, role="customer", **extra_fields):
        if not phone:
            raise ValueError("Users must have a phone number")
        phone = str(phone).strip()
        user = self.model(phone=phone, role=role, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("role", "admin")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(phone, password, **extra_fields)


# ----------------------------------------
# USER MODEL
# ----------------------------------------
class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("employee", "Employee"),
        ("customer", "Customer"),
    ]

    phone = models.CharField(
        max_length=15, unique=True, validators=[iraq_phone_validator]
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="customer")

    # Account states
    is_active = models.BooleanField(default=False)  # customers start inactive
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return f"{self.phone} ({self.role})"

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_employee(self):
        return self.role == "employee"

    @property
    def is_customer(self):
        return self.role == "customer"


class ShippingAddress(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="shipping_address"
    )
    full_name = models.CharField(max_length=255)
    city_id = models.IntegerField()
    city = models.CharField(max_length=50)
    region_id = models.IntegerField()
    region = models.CharField(max_length=50)
    location = models.TextField()
    client_mobile2 = models.CharField(
        max_length=15,
        unique=True,
        validators=[iraq_phone_validator],
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.user.phone + " " + self.full_name


class OTPVerification(models.Model):
    PURPOSE_CHOICES = [
        ("activation", "Account Activation"),
        ("password_reset", "Password Reset"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otps")
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"OTP {self.otp_code} for {self.user.phone} ({self.purpose})"

    @staticmethod
    def generate_code():
        """Generate a random 6-digit OTP."""
        return str(random.randint(100000, 999999))

    @classmethod
    def create_otp(cls, user, purpose):
        """Generate and store OTP for a specific purpose."""
        # Clear expired or old OTPs
        cls.objects.filter(
            user=user, purpose=purpose, is_used=False, expires_at__lt=timezone.now()
        ).delete()
        code = cls.generate_code()
        expires = timezone.now() + timedelta(minutes=5)
        otp = cls.objects.create(
            user=user, otp_code=code, purpose=purpose, expires_at=expires
        )
        return otp

    @classmethod
    def last_sent(cls, user, purpose):
        """Return the last OTP entry (if exists)."""
        return (
            cls.objects.filter(user=user, purpose=purpose)
            .order_by("-created_at")
            .first()
        )

    def is_expired(self):
        return timezone.now() > self.expires_at

    def verify(self, code):
        """Validate OTP."""
        if self.is_used:
            return False
        if timezone.now() > self.expires_at:
            return False
        if self.otp_code != code:
            return False
        self.is_used = True
        self.save()
        return True
