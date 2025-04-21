from abc import ABC, abstractmethod
import importlib

class BasePlugin(ABC):
    def __init__(self, config):
        self.config = config

    @classmethod
    def load(cls, config):
        module_name, class_name = config.module_path.rsplit('.', 1)
        module = importlib.import_module(module_name)
        plugin_class = getattr(module, class_name)
        return plugin_class(config.config)

class PaymentPlugin(BasePlugin):
    @abstractmethod
    def initiate_payment(self, amount, phone, invoice_id, customer_id):
        pass

    @abstractmethod
    def check_payment_status(self, transaction_id):
        pass

class MessagingPlugin(BasePlugin):
    @abstractmethod
    def send_message(self, phone, message):
        pass

class NetworkingPlugin(BasePlugin):
    @abstractmethod
    def sync_credentials(self, router, username, password, profile, limit_uptime):
        pass