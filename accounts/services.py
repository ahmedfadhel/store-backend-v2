from django.utils import timezone
from django.core.cache import cache
from .models import OTPVerification
from .utils import send_whatsapp_message


class OTPService:
    COOLDOWN_SECONDS = 60
    EXPIRY_MINUTES = 5
    MAX_VERIFY_ATTEMPTS = 5
    BLOCK_SECONDS = 10 * 60  # 10 minutes

    @classmethod
    def send_otp(cls, user, purpose):
        """Send OTP if cooldown allows."""
        last_otp = OTPVerification.last_sent(user, purpose)
        if last_otp:
            delta = timezone.now() - last_otp.created_at
            if delta.total_seconds() < cls.COOLDOWN_SECONDS:
                remaining = max(0, cls.COOLDOWN_SECONDS - int(delta.total_seconds()))
                return {
                    "success": False,
                    "message": f"Please wait {remaining}s before requesting another OTP.",
                }

        if last_otp and last_otp.is_expired():
            last_otp.is_used = True
            last_otp.save(update_fields=["is_used"])

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

    @classmethod
    def verify_with_attempt_limit(cls, user, purpose, code):
        """
        Validate OTP with an attempt cap to mitigate brute-force attacks.
        """
        cache_key = f"otp_verify_attempts:{purpose}:{user.phone}"
        attempts = cache.get(cache_key, 0)
        if attempts >= cls.MAX_VERIFY_ATTEMPTS:
            return {
                "success": False,
                "message": "Too many OTP attempts. Please wait and try again.",
            }

        result = cls.verify_otp(user, purpose, code)
        if result["success"]:
            cache.delete(cache_key)
            return result

        cache.set(cache_key, attempts + 1, cls.BLOCK_SECONDS)
        return result
