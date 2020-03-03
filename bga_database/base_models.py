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

    def clean(self):
        try:
            preferred_aliases = type(self).objects.filter(
                Q(preferred=True) & Q(employer_id=self.employer.id)
            )
        except len(preferred_aliases) == 0:
            self.preferred = True
        except len(preferred_aliases) > 1:
            other_alias = preferred_aliases.filter(~Q(id=self.id)).first()
            other_alias.preferred = False
            other_alias.save()

            self.preferred = True
