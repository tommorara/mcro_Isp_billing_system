from django_tenants.middleware import TenantMiddleware
from django.http import Http404
from companies.models import Domain

class SimpleTenantMiddleware(TenantMiddleware):
    def get_tenant(self, request):
        hostname = request.get_host().split(':')[0]
        if hostname == 'localhost':  # Fallback for public schema
            return None
        try:
            domain = Domain.objects.get(domain=hostname)
            return domain.tenant
        except Domain.DoesNotExist:
            raise Http404("Invalid tenant")