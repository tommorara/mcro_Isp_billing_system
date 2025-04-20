from rest_framework import serializers
from .models import Customer, Package, Subscription

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name', 'email', 'phone', 'address']

class PackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Package
        fields = ['id', 'name', 'connection_type', 'speed', 'price', 'duration_days', 'duration_hours']

class SubscriptionSerializer(serializers.ModelSerializer):
    package = PackageSerializer()
    class Meta:
        model = Subscription
        fields = ['id', 'package', 'connection_type', 'username', 'start_date', 'end_date', 'is_active', 'router', 'static_ip']