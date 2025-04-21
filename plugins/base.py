import logging

logger = logging.getLogger(__name__)

class BaseSMSPlugin:
    def __init__(self, config):
        self.config = config

    def send_sms(self, to, message):
        """Implement SMS sending logic in subclasses."""
        raise NotImplementedError("SMS plugin must implement send_sms method")

class PaymentPlugin:
    def __init__(self, config):
        self.config = config

    def initiate_payment(self, amount, phone, invoice_id, customer_id):
        """Implement payment initiation logic in subclasses."""
        raise NotImplementedError("Payment plugin must implement initiate_payment method")