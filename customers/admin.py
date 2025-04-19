from django.contrib import admin
from customers.models import Customer, BillingRecord

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'data_usage', 'created_at')
    search_fields = ('full_name', 'email')

@admin.register(BillingRecord)
class BillingRecordAdmin(admin.ModelAdmin):
    list_display = ('customer', 'amount', 'billed_at', 'paid')
    list_filter = ('paid',)