from django.urls import path
from .views import (
    RegisterView,
    VerifyOTPView,
    LoginView,
    # ProfileView,
    ResendOTPView,
    RequestResetView,
    ResetPasswordView,
)

urlpatterns = [
    path("register", RegisterView.as_view(), name="register"),
    path("verify-otp", VerifyOTPView.as_view(), name="verify-otp"),
    path("login", LoginView.as_view(), name="login"),
    path("resend-otp/", ResendOTPView.as_view(), name="resend-otp"),
    path("request-reset", RequestResetView.as_view(), name="request-reset"),
    path("reset-password", ResetPasswordView.as_view(), name="reset-password"),
]
