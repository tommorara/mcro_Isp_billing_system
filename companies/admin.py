from django.contrib import admin
from .models import Company

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'hotspot_login_method', 'country', 'currency', 'created_at']
    search_fields = ['name', 'email', 'phone']
    list_filter = ['hotspot_login_method', 'country', 'currency', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (None, {
            'fields': (
                'name',
                'email',
                'phone',
                'address',
                'hotspot_login_method',
                'country',
                'currency'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )