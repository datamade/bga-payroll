from django.db import models


class SluggedModel(models.Model):
    slug = models.SlugField(max_length=255, unique=True, null=True)

    class Meta:
        abstract = True
