from django.db import models
import importlib
import logging

logger = logging.getLogger(__name__)

class PluginConfig(models.Model):
    PLUGIN_TYPES = (
        ('PAYMENT', 'Payment'),
        ('SMS', 'SMS'),
    )
    name = models.CharField(max_length=100, unique=True)
    plugin_type = models.CharField(max_length=20, choices=PLUGIN_TYPES)
    module_path = models.CharField(max_length=200, help_text="Python module path (e.g., plugins.sms.twilio_plugin)")
    config = models.JSONField(default=dict, blank=True, help_text="Configuration JSON (e.g., API keys)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.plugin_type})"

    def load(self):
        """Dynamically load the plugin class."""
        try:
            module_name, class_name = self.module_path.rsplit('.', 1)
            module = importlib.import_module(module_name)
            plugin_class = getattr(module, class_name)
            return plugin_class(self)
        except Exception as e:
            logger.error(f"Failed to load plugin {self.name}: {e}")
            raise