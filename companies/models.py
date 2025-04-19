from django.db import models
from django_tenants.models import TenantMixin, DomainMixin

class Company(TenantMixin):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    auto_create_schema = True

    def __str__(self):
        return self.name

class Domain(DomainMixin):
    pass

class TenantSettings(models.Model):
    tenant = models.OneToOneField(Company, on_delete=models.CASCADE)
    enable_kyc = models.BooleanField(default=False)
    branding = models.JSONField(default=dict)