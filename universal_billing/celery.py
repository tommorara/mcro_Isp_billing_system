import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'universal_billing.settings')

app = Celery('universal_billing')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()