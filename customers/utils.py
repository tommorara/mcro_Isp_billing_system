import string
import random
import logging
from django.core.mail import send_mail
from django.conf import settings
from plugins.models import PluginConfig

logger = logging.getLogger(__name__)

def generate_voucher_codes(count, length, char_type, prefix=''):
    """Generate unique voucher codes."""
    codes = set()
    chars = {
        'uppercase': string.ascii_uppercase,
        'lowercase': string.ascii_lowercase,
        'numbers': string.digits,
        'random': string.ascii_letters + string.digits
    }[char_type]
    
    while len(codes) < count:
        code = ''.join(random.choice(chars) for _ in range(length))
        full_code = f"{prefix}{code}"
        codes.add(full_code)
    
    return list(codes)

def send_sms(to, message):
    """Send SMS using the active SMS plugin."""
    plugin_config = PluginConfig.objects.filter(plugin_type='SMS', is_active=True).first()
    if not plugin_config:
        logger.error("No active SMS plugin configured")
        return {'status': 'error', 'error': 'No active SMS plugin configured'}
    
    try:
        plugin = plugin_config.load()
        return plugin.send_sms(to, message)
    except Exception as e:
        logger.error(f"Failed to send SMS to {to}: {e}")
        return {'status': 'error', 'error': str(e)}

def send_email(to, subject, message):
    """Send email using Django's email system."""
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [to],
            fail_silently=False,
        )
        logger.info(f"Sent email to {to}: {subject}")
        return {'status': 'success'}
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return {'status': 'error', 'error': str(e)}