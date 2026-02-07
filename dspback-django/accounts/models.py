from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user with ORCID as the primary identifier."""

    orcid = models.CharField(max_length=64, unique=True, db_index=True)
    orcid_access_token = models.TextField(blank=True, null=True)

    USERNAME_FIELD = "orcid"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "auth_user"

    def __str__(self):
        return self.orcid
