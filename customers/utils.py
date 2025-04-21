import string
import secrets
import logging
from django.db import IntegrityError
from .models import Voucher

logger = logging.getLogger(__name__)

def generate_voucher_codes(count=1, length=6, char_type='uppercase', prefix=''):
    """
    Generate unique voucher codes.
    :param count: Number of vouchers (default: 1)
    :param length: Length of random part (default: 6)
    :param char_type: 'uppercase', 'lowercase', 'numbers', 'random'
    :param prefix: Optional prefix (e.g., 'ISP-')
    :return: List of voucher codes
    """
    logger.info(f"Attempting to generate {count} voucher codes with length {length}, char_type {char_type}, prefix {prefix}")
    chars = {
        'uppercase': string.ascii_uppercase,
        'lowercase': string.ascii_lowercase,
        'numbers': string.digits,
        'random': string.ascii_letters + string.digits
    }
    char_set = chars.get(char_type, string.ascii_uppercase)
    codes = []
    attempts = 0
    max_attempts = count * 10

    while len(codes) < count and attempts < max_attempts:
        try:
            code = ''.join(secrets.choice(char_set) for _ in range(length))
            full_code = f"{prefix}{code}"
            if not Voucher.objects.filter(code=full_code).exists():
                codes.append(full_code)
                logger.debug(f"Generated unique code: {full_code}")
            else:
                logger.debug(f"Code collision: {full_code}")
        except Exception as e:
            logger.error(f"Error generating code: {e}")
        attempts += 1

    if len(codes) < count:
        logger.error(f"Could only generate {len(codes)} of {count} voucher codes due to collisions after {attempts} attempts")
        raise ValueError(f"Could only generate {len(codes)} of {count} voucher codes")

    logger.info(f"Successfully generated {len(codes)} voucher codes")
    return codes