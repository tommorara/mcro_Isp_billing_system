from django.db import models

class Company(models.Model):
    HOTSPOT_LOGIN_METHODS = (
        ('TRANSACTION', 'M-Pesa Transaction Code'),
        ('PHONE', 'Phone Number'),
        ('VOUCHER', 'Voucher Code'),
    )
    CURRENCY_CHOICES = (
        ('KES', 'Kenyan Shilling (KSh)'),
        ('USD', 'US Dollar ($)'),
        ('EUR', 'Euro (€)'),
    )
    COUNTRY_CHOICES = (
        ('KE', 'Kenya (+254)'),
        ('US', 'United States (+1)'),
        ('UK', 'United Kingdom (+44)'),
    )
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    hotspot_login_method = models.CharField(
        max_length=20,
        choices=HOTSPOT_LOGIN_METHODS,
        default='TRANSACTION',
        help_text="Default login method for Hotspot users"
    )
    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES, default='KE')
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='KES')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_country_code(self):
        """Return the phone country code based on country."""
        return {
            'KE': '+254',
            'US': '+1',
            'UK': '+44',
        }.get(self.country, '+254')