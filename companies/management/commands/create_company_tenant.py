from django.core.management.base import BaseCommand
from companies.models import Company, Domain, TenantSettings

class Command(BaseCommand):
    help = 'Create a new tenant for a company'

    def add_arguments(self, parser):
        parser.add_argument('--subdomain', required=True)
        parser.add_argument('--name', required=True)
        parser.add_argument('--email', required=True)

    def handle(self, *args, **options):
        tenant = Company.objects.create(
            schema_name=options['subdomain'],
            name=options['name'],
            email=options['email']
        )
        Domain.objects.create(domain=f"{options['subdomain']}.localhost", tenant=tenant, is_primary=True)
        TenantSettings.objects.create(tenant=tenant)
        self.stdout.write(self.style.SUCCESS(f'Tenant {tenant.name} created'))