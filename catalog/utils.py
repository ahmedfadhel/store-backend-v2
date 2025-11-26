from django.db import models
from django.utils.text import slugify


def unique_slugify(instance, text, slug_field_name="slug"):
    """
    Generates a unique slug from any text (Arabic supported).
    """
    slug = slugify(text, allow_unicode=True)
    ModelClass = instance.__class__
    print("I here")
    # Check if slug exists
    counter = 1
    unique_slug = slug
    while (
        ModelClass.objects.filter(**{slug_field_name: unique_slug})
        .exclude(pk=instance.pk)
        .exists()
    ):
        print("here")
        unique_slug = f"{slug}-{counter}"
        counter += 1

    return unique_slug
