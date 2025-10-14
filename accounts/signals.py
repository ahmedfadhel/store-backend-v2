# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from .models import User, OTPVerification
# from .utils import send_whatsapp_message


# @receiver(post_save, sender=User)
# def send_activation_otp(sender, instance, created, **kwargs):
#     if created and instance.role == "customer" and not instance.is_active:
#         otp_entry = OTPVerification.create_otp(instance, purpose="activation")
#         send_whatsapp_message(
#             instance.phone, f"Your Shoplite activation code is {otp_entry.otp_code}"
#         )
