from ..base import BaseSMSPlugin
from twilio.rest import Client
import logging

logger = logging.getLogger(__name__)

class TwilioSMSPlugin(BaseSMSPlugin):
    def __init__(self, config):
        super().__init__(config)
        self.client = Client(
            self.config.config.get('account_sid'),
            self.config.config.get('auth_token')
        )
        self.from_number = self.config.config.get('from_number')

    def send_sms(self, to, message):
        try:
            message = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to
            )
            logger.info(f"Sent SMS to {to} via Twilio: {message.sid}")
            return {'status': 'success', 'message_id': message.sid}
        except Exception as e:
            logger.error(f"Failed to send SMS to {to} via Twilio: {e}")
            return {'status': 'error', 'error': str(e)}