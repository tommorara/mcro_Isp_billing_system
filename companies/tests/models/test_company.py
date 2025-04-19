from django.test import TestCase
from django_tenants.utils import get_tenant_model

class CompanyTests(TestCase):
    def test_create_tenant(self):
        tenant = get_tenant_model().objects.create(
            schema_name='isp1', name='ISP One', email='admin@isp1.com'
        )
        self.assertEqual(tenant.name, 'ISP One')
        self.assertEqual(tenant.schema_name, 'isp1')