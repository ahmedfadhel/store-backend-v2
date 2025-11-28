from django.contrib import admin

# Register your models here.


from .models import User, OTPVerification, ShippingAddress

admin.site.register(User)
admin.site.register(OTPVerification)
admin.site.register(ShippingAddress)
