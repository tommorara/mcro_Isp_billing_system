from django.db import models

class Company(models.Model):
    HOTSPOT_LOGIN_METHODS = (
        ('TRANSACTION', 'M-Pesa Transaction Code'),
        ('PHONE', 'Phone Number'),
        ('VOUCHER', 'Voucher Code'),
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name