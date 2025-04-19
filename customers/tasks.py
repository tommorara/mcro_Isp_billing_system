# customers/tasks.py
from celery import shared_task
from django_tenants.utils import tenant_context
from companies.models import Company
from customers.models import Customer

@shared_task
def calculate_usage(tenant_id):
    tenant = Company.objects.get(id=tenant_id)
    with tenant_context(tenant):
        # Fetch MikroTik data
        for customer in Customer.objects.all():
            customer.data_usage += 100  # Example
            customer.save()