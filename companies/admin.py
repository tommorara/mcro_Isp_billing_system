from django.contrib import admin
from .models import Company

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'hotspot_login_method', 'created_at']
    search_fields = ['name', 'email']
    list_filter = ['hotspot_login_method', 'created_at']
    readonly_fields = ['created_at', 'updated_at']