# companies/tasks.py
from celery import shared_task

@shared_task
def calculate_usage(tenant_id):
    # Fetch MikroTik data (March 2025 expertise)
    pass