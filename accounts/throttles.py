from rest_framework.throttling import SimpleRateThrottle


class OTPBurstRateThrottle(SimpleRateThrottle):
    scope = "otp"

    def get_cache_key(self, request, view):
        # Use IP address as key for unauthenticated OTP requests
        return self.get_ident(request)


class OTPVerifyRateThrottle(SimpleRateThrottle):
    """
    Throttle OTP verification attempts by phone number (fallback to IP).
    """

    scope = "otp_verify"

    def get_cache_key(self, request, view):
        phone = request.data.get("phone") if hasattr(request, "data") else None
        if phone:
            ident = str(phone).strip()
            return self.cache_format % {"scope": self.scope, "ident": ident}
        return self.get_ident(request)
