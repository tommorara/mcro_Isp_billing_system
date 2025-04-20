from django.contrib import admin
from .models import Router, Package, Customer, Subscription, Invoice, SessionLog, SupportMessage
from django.contrib.auth.hashers import make_password

@admin.register(Router)
class RouterAdmin(admin.ModelAdmin):
    list_display = ('name', 'ip_address', 'username', 'vpn_server')
    search_fields = ('name', 'ip_address')

@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'connection_type', 'speed', 'price', 'duration_days', 'duration_hours')
    search_fields = ('name', 'speed')
    list_filter = ('connection_type',)

    def save_model(self, request, obj, form, change):
        if (obj.duration_days and obj.duration_hours) or (not obj.duration_days and not obj.duration_hours):
            raise ValueError("Package must have either duration_days or duration_hours, not both or neither.")
        super().save_model(request, obj, form, change)

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'company')
    search_fields = ('name', 'email', 'phone')
    list_filter = ('company',)

    def save_model(self, request, obj, form, change):
        if 'password' in form.changed_data and obj.password:
            obj.password = make_password(obj.password)
        elif not change and not obj.password:
            obj.password = make_password('pass123')
        super().save_model(request, obj, form, change)

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('customer', 'package', 'connection_type', 'username', 'is_active', 'start_date', 'end_date')
    search_fields = ('customer__name', 'username')
    list_filter = ('connection_type', 'is_active', 'router')

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'subscription', 'amount', 'issued_date', 'status')
    search_fields = ('customer__name', 'transaction_id')
    list_filter = ('status', 'issued_date')

@admin.register(SessionLog)
class SessionLogAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'login_time', 'logout_time', 'bytes_in', 'bytes_out')
    search_fields = ('subscription__username',)
    list_filter = ('login_time',)

@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'customer', 'created_at', 'is_read')
    search_fields = ('subject', 'customer__name')
    list_filter = ('is_read', 'created_at')