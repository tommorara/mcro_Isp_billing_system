from django.db import models

class PluginConfig(models.Model):
    PLUGIN_TYPES = (
        ('PAYMENT', 'Payment Gateway'),
        ('MESSAGING', 'Messaging (SMS/WhatsApp)'),
        ('NETWORKING', 'Networking API'),
    )
    name = models.CharField(max_length=100, unique=True)
    plugin_type = models.CharField(max_length=20, choices=PLUGIN_TYPES)
    module_path = models.CharField(max_length=200)  # e.g., 'plugins.payments.mpesa.MpesaPlugin'
    config = models.JSONField(default=dict)  # e.g., {'api_key': '...', 'secret': '...'}
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.plugin_type})"