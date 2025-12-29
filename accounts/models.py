from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
import secrets
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from carts.models import Cart
from django.utils import timezone
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
        # Strip privilege-related fields to avoid elevation through serializers
        extra_fields.pop("is_staff", None)
        extra_fields.pop("is_superuser", None)
        extra_fields.pop("is_active", None)
        role = role if role in {"customer", "employee"} else "customer"
        user = self.model(phone=phone, role=role, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("Superusers must have a phone number")
        phone = str(phone).strip()
        extra_fields.setdefault("role", "admin")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


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


@receiver(post_save, sender=User)
def create_user_cart(sender, instance, created, *args, **kwargs):
    if created:
        Cart.objects.create(user=instance)


class ShippingAddress(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
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

    def has_shipping_info(self) -> bool:
        return bool(self.city_id and self.region_id)


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
        """Generate a cryptographically secure random 6-digit OTP."""
        return str(secrets.randbelow(900000) + 100000)

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
