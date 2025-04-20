from django.db import models
from companies.models import Company

class Router(models.Model):
    name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    vpn_server = models.CharField(max_length=100, blank=True, null=True, help_text="VPN server address (e.g., for PPTP/L2TP)")

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(fields=['ip_address']),
        ]

class Package(models.Model):
    CONNECTION_TYPES = (
        ('HOTSPOT', 'Hotspot'),
        ('PPPOE', 'PPPoE'),
        ('STATIC', 'Static'),
        ('VPN', 'VPN'),
    )
    name = models.CharField(max_length=100)
    connection_type = models.CharField(max_length=20, choices=CONNECTION_TYPES)  # Temporary null=True
    speed = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(blank=True, null=True, help_text="Days for long-term plans")
    duration_hours = models.IntegerField(blank=True, null=True, help_text="Hours for short-term plans (e.g., Hotspot)")

    def __str__(self):
        duration = f"{self.duration_hours} hours" if self.duration_hours else f"{self.duration_days} days"
        return f"{self.name} ({self.speed}, {self.connection_type}, {duration})"

    class Meta:
        indexes = [
            models.Index(fields=['connection_type']),
        ]

class Customer(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    address = models.TextField(blank=True)
    password = models.CharField(max_length=128, null=False, blank=False)

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(fields=['email']),
        ]

class Subscription(models.Model):
    CONNECTION_TYPES = (
        ('HOTSPOT', 'Hotspot'),
        ('PPPOE', 'PPPoE'),
        ('STATIC', 'Static'),
        ('VPN_PPT', 'VPN (PPTP)'),
        ('VPN_L2TP', 'VPN (L2TP)'),
        ('VPN_OVPN', 'VPN (OpenVPN)'),
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    connection_type = models.CharField(max_length=20, choices=CONNECTION_TYPES)
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    router = models.ForeignKey(Router, on_delete=models.SET_NULL, null=True)
    static_ip = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.customer.name} - {self.package.name}"

    class Meta:
        indexes = [
            models.Index(fields=['end_date']),
            models.Index(fields=['username']),
            models.Index(fields=['router']),
            models.Index(fields=['static_ip']),
        ]

class Invoice(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    issued_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=(('PENDING', 'Pending'), ('PAID', 'Paid'), ('FAILED', 'Failed')))
    transaction_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Invoice {self.id} for {self.customer.name}"

    class Meta:
        indexes = [
            models.Index(fields=['issued_date']),
        ]

class SessionLog(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    login_time = models.DateTimeField()
    logout_time = models.DateTimeField(null=True, blank=True)
    bytes_in = models.BigIntegerField(default=0)
    bytes_out = models.BigIntegerField(default=0)

    def __str__(self):
        return f"Session for {self.subscription.username} at {self.login_time}"

    class Meta:
        indexes = [
            models.Index(fields=['login_time']),
        ]

class SupportMessage(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.subject} for {self.customer.name}"

    class Meta:
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['is_read']),
        ]