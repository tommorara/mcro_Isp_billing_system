from rest_framework import serializers
from .models import Customer, Package, Subscription, Voucher

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'company', 'name', 'email', 'phone', 'address', 'created_at']

class PackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Package
        fields = ['id', 'name', 'connection_type', 'download_bandwidth', 'upload_bandwidth', 'price', 'duration_minutes', 'duration_hours', 'duration_days']

class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ['id', 'customer', 'package', 'connection_type', 'username', 'start_date', 'end_date', 'is_active']

class VoucherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Voucher
        fields = ['id', 'package', 'code', 'prefix', 'is_active', 'redeemed_at']