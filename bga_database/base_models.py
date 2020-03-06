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
        preferred_aliases = entity.aliases.filter(
            Q(preferred=True) & Q(id=entity.id)
        )

        if len(preferred_aliases) >= 1 and self.preferred:
            other_alias = preferred_aliases.filter(~Q(id=self.id) & Q(preferred=True)).first()
            other_alias.preferred = False
            other_alias.save()
