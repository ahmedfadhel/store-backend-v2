from django.utils import timezone
from datetime import timedelta
from .models import OTPVerification
from .utils import send_whatsapp_message


class OTPService:
    COOLDOWN_SECONDS = 60
    EXPIRY_MINUTES = 5

    @classmethod
    def can_send_otp(cls, user, purpose):
        """Check if cooldown period has passed."""
        last_otp = OTPVerification.last_sent(user, purpose)
        if not last_otp:
            return True
        delta = timezone.now() - last_otp.created_at
        return delta.total_seconds() >= cls.COOLDOWN_SECONDS

    @classmethod
    def send_otp(cls, user, purpose):
        """Send OTP if cooldown allows."""
        if not cls.can_send_otp(user, purpose):
            remaining = cls.COOLDOWN_SECONDS - int(
                (
                    timezone.now() - OTPVerification.last_sent(user, purpose).created_at
                ).total_seconds()
            )
            return {
                "success": False,
                "message": f"Please wait {remaining}s before requesting another OTP.",
            }

        # Create OTP entry
        otp = OTPVerification.create_otp(user, purpose)
        message = (
            f"Your Shoplite {'activation' if purpose=='activation' else 'password reset'} code is {otp.otp_code}. "
            f"It expires in {cls.EXPIRY_MINUTES} minutes."
        )
        send_whatsapp_message(user.phone, message)

        return {
            "success": True,
            "message": f"OTP sent successfully to {user.phone} via WhatsApp.",
            "expires_in": f"{cls.EXPIRY_MINUTES} minutes",
        }

    @classmethod
    def verify_otp(cls, user, purpose, code):
        """Validate an OTP for a specific purpose."""
        otp_entry = (
            OTPVerification.objects.filter(user=user, purpose=purpose, is_used=False)
            .order_by("-created_at")
            .first()
        )

        if not otp_entry:
            return {"success": False, "message": "No active OTP found."}

        if otp_entry.is_expired():
            return {"success": False, "message": "OTP expired."}

        if otp_entry.otp_code != code:
            return {"success": False, "message": "Invalid OTP."}

        otp_entry.is_used = True
        otp_entry.save()
        return {"success": True, "message": "OTP verified successfully."}
