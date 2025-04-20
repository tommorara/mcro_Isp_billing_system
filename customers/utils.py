import string
import secrets

def generate_voucher_codes(count=1, length=6, char_type='uppercase', prefix=''):
    """
    Generate voucher codes.
    :param count: Number of vouchers (default: 1)
    :param length: Length of random part (default: 6)
    :param char_type: 'uppercase', 'lowercase', 'numbers', 'random'
    :param prefix: Optional prefix (e.g., 'ISP-')
    :return: List of voucher codes
    """
    chars = {
        'uppercase': string.ascii_uppercase,
        'lowercase': string.ascii_lowercase,
        'numbers': string.digits,
        'random': string.ascii_letters + string.digits
    }
    char_set = chars.get(char_type, string.ascii_uppercase)
    codes = []
    for _ in range(count):
        code = ''.join(secrets.choice(char_set) for _ in range(length))
        codes.append(f"{prefix}{code}")
    return codes