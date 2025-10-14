from rest_framework.throttling import SimpleRateThrottle


class OTPBurstRateThrottle(SimpleRateThrottle):
    scope = "otp"

    def get_cache_key(self, request, view):
        # Use IP address as key for unauthenticated OTP requests
        return self.get_ident(request)
