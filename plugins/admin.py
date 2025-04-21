from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import PluginConfig

@admin.register(PluginConfig)
class PluginConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'plugin_type', 'is_active', 'created_at']
    search_fields = ['name', 'plugin_type']
    list_filter = ['plugin_type', 'is_active']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (None, {
            'fields': ('name', 'plugin_type', 'module_path', 'config', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )