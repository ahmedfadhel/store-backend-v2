from django.contrib import admin
from .models import ReturnRequest, ReturnRequestLine

# Register your models here.


admin.site.register(ReturnRequest)
admin.site.register(ReturnRequestLine)
