from django.contrib import admin
from .models import *

# Register your models here.


admin.site.register(Product)
admin.site.register(VariantOption)
admin.site.register(VariantOptionValue)
admin.site.register(ProductVariant)
admin.site.register(TieredPrice)
admin.site.register(ProductImage)
admin.site.register(Bundle)
admin.site.register(BundleItem)
