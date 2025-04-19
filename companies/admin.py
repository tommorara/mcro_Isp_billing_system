from django.contrib import admin
from companies.models import Company, Domain, TenantSettings

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'created_at', 'schema_name')
    search_fields = ('name', 'email')

@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'tenant', 'is_primary')
    search_fields = ('domain',)

@admin.register(TenantSettings)
class TenantSettingsAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'enable_kyc')
    list_filter = ('enable_kyc',)