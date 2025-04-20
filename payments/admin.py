from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'customer', 'invoice', 'amount', 'payment_method', 'status', 'created_at')
    search_fields = ('transaction_id', 'customer__name')
    list_filter = ('status', 'payment_method', 'created_at')