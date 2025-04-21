from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from companies.models import Company

class Customer(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    address = models.TextField(blank=True)
    password = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.password and not self.password.startswith('pbkdf2_sha256$'):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

class AuditLog(models.Model):
    action = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    object_id = models.CharField(max_length=36)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} on {self.model} {self.object_id}"

class Location(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Router(models.Model):
    CONNECTION_TYPES = (
        ('API', 'MikroTik API'),
        ('RADIUS', 'RADIUS Server'),
        ('VPN', 'VPN Tunnel'),
    )
    VPN_PROTOCOLS = (
        ('OPENVPN', 'OpenVPN'),
        ('PPTP', 'PPTP'),
        ('L2TP', 'L2TP'),
        ('WIREGUARD', 'WireGuard'),
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    connection_type = models.CharField(
        max_length=20,
        choices=CONNECTION_TYPES,
        default='API'
    )
    ip_address = models.CharField(max_length=45, blank=True)
    username = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=128, blank=True)
    api_port = models.IntegerField(default=8728, blank=True, null=True)
    radius_server = models.CharField(max_length=45, blank=True)
    radius_secret = models.CharField(max_length=128, blank=True)
    vpn_server = models.CharField(max_length=45, blank=True)
    vpn_protocol = models.CharField(
        max_length=20,
        choices=VPN_PROTOCOLS,
        blank=True
    )
    vpn_username = models.CharField(max_length=100, blank=True)
    vpn_password = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Package(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    router = models.ForeignKey(Router, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    connection_type = models.CharField(
        max_length=20,
        choices=(
            ('HOTSPOT', 'Hotspot'),
            ('PPPOE', 'PPPoE'),
            ('STATIC', 'Static'),
            ('VPN', 'VPN'),
        )
    )
    download_bandwidth = models.IntegerField()
    upload_bandwidth = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.IntegerField(blank=True, null=True)
    duration_hours = models.IntegerField(blank=True, null=True)
    duration_days = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['connection_type']),
            models.Index(fields=['router']),
            models.Index(fields=['location']),
        ]

    def __str__(self):
        return self.name

class Subscription(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    connection_type = models.CharField(
        max_length=20,
        choices=(
            ('HOTSPOT', 'Hotspot'),
            ('PPPOE', 'PPPoE'),
            ('STATIC', 'Static'),
            ('VPN', 'VPN'),
        )
    )
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=128)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    router = models.ForeignKey(Router, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.customer.name} - {self.package.name}"

class SessionLog(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    username = models.CharField(max_length=100)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(blank=True, null=True)
    data_used = models.BigIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['username', 'start_time']),
            models.Index(fields=['subscription']),
        ]

    def __str__(self):
        return f"Session for {self.username} at {self.start_time}"

class Invoice(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=(
            ('PENDING', 'Pending'),
            ('PAID', 'Paid'),
            ('FAILED', 'Failed'),
        ),
        default='PENDING'
    )
    issued_date = models.DateTimeField(auto_now_add=True)
    paid_date = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Invoice {self.id} for {self.customer.name}"

class Compensation(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    reason = models.TextField()
    duration_minutes = models.IntegerField(blank=True, null=True)
    duration_hours = models.IntegerField(blank=True, null=True)
    duration_days = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Compensation for {self.customer.name}"

class SupportMessage(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_admin_reply = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Support message from {self.customer.name}: {self.subject}"

class Voucher(models.Model):
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    code = models.CharField(max_length=20, unique=True)
    prefix = models.CharField(max_length=10, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    redeemed_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['code']),
        ]

    def __str__(self):
        return self.code