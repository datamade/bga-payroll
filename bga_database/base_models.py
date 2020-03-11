from django.db import models
from django.db.models import Q


class SluggedModel(models.Model):
    slug = models.SlugField(max_length=255, unique=True, null=True)

    class Meta:
        abstract = True


class AliasModel(models.Model):
    name = models.CharField(max_length=255)
    preferred = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()

        entity = getattr(self, self.entity_type)
        preferred_alias = entity.aliases.filter(preferred=True)

        if len(preferred_alias) == 1 and self.preferred:
            preferred_alias.update(preferred=False)

    def save(self, * args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
