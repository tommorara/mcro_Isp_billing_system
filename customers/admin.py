from django.contrib import admin
from django import forms
from django.urls import reverse, path
from django.utils.html import format_html
from django.shortcuts import redirect, render
from django.contrib import messages
from .models import Customer, AuditLog, Location, Router, Package, Subscription, SessionLog, Invoice, Compensation, SupportMessage, Voucher
from .utils import generate_voucher_codes
import routeros_api
import MySQLdb
import logging

logger = logging.getLogger(__name__)

class CustomerAdminForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = '__all__'

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data['password'] and not self.cleaned_data['password'].startswith('pbkdf2_sha256$'):
            instance.password = make_password(self.cleaned_data['password'])
        if commit:
            instance.save()
        return instance

class GenerateVouchersForm(forms.Form):
    count = forms.IntegerField(min_value=1, initial=1, label="Number of Vouchers")
    length = forms.IntegerField(min_value=4, initial=6, label="Code Length")
    char_type = forms.ChoiceField(
        choices=(
            ('uppercase', 'Uppercase Letters'),
            ('lowercase', 'Lowercase Letters'),
            ('numbers', 'Numbers'),
            ('random', 'Letters + Numbers')
        ),
        initial='uppercase',
        label="Character Type"
    )
    prefix = forms.CharField(max_length=10, required=False, label="Prefix (e.g., ISP-)")
    package = forms.ModelChoiceField(queryset=Package.objects.all(), label="Package")

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    form = CustomerAdminForm
    list_display = ['name', 'email', 'phone', 'company', 'created_at']
    search_fields = ['name', 'email', 'phone']
    list_filter = ['company', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (None, {
            'fields': (
                'company',
                'name',
                'email',
                ('phone', 'phone_help'),
                'address',
                'password'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    list_display_links = ['name', 'email']

    def phone_help(self, obj):
        return format_html(
            '<span class="tooltip"><span class="icon-info">ℹ</span><span class="tooltiptext">Enter phone in format +254xxxxxxxxx</span></span>'
        )
    phone_help.short_description = ''

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'model', 'object_id', 'user', 'created_at']
    search_fields = ['action', 'model', 'object_id']
    list_filter = ['action', 'created_at']
    readonly_fields = ['created_at']

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'address', 'created_at']
    search_fields = ['name', 'address']
    list_filter = ['company', 'created_at']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Router)
class RouterAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'connection_type', 'vpn_protocol', 'ip_address', 'created_at']
    search_fields = ['name', 'ip_address']
    list_filter = ['location', 'connection_type', 'vpn_protocol', 'created_at']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'connection_type', 'price', 'download_bandwidth', 'company', 'created_at']
    search_fields = ['name']
    list_filter = ['connection_type', 'company', 'location', 'created_at']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['customer', 'package', 'connection_type', 'username', 'is_active', 'created_at']
    search_fields = ['customer__name', 'username']
    list_filter = ['connection_type', 'is_active', 'created_at']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(SessionLog)
class SessionLogAdmin(admin.ModelAdmin):
    list_display = ['subscription', 'username', 'start_time', 'end_time', 'data_used', 'created_at']
    search_fields = ['username']
    list_filter = ['start_time', 'created_at']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['customer', 'amount', 'status', 'issued_date', 'created_at', 'sales_report']
    search_fields = ['customer__name']
    list_filter = ['status', 'issued_date', 'created_at']
    readonly_fields = ['created_at', 'updated_at']

    def sales_report(self, obj):
        return format_html(
            '<a href="{}">Daily Sales</a> | <a href="{}">Monthly Sales</a>',
            reverse('daily_sales_report'),
            reverse('monthly_sales_report')
        )
    sales_report.short_description = 'Sales Reports'

@admin.register(Compensation)
class CompensationAdmin(admin.ModelAdmin):
    list_display = ['customer', 'subscription', 'duration_days', 'duration_hours', 'created_at']
    search_fields = ['customer__name', 'reason']
    list_filter = ['created_at']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ['customer', 'subject', 'is_admin_reply', 'is_read', 'created_at']
    search_fields = ['subject', 'message']
    list_filter = ['is_admin_reply', 'is_read', 'created_at']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ['code', 'prefix', 'package', 'is_active', 'redeemed_at', 'created_at']
    search_fields = ['code', 'prefix']
    list_filter = ['is_active', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['generate_vouchers']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('generate-vouchers/', self.admin_site.admin_view(self.generate_vouchers_view), name='voucher_generate'),
        ]
        return custom_urls + urls

    def generate_vouchers_view(self, request):
        logger.info("Accessing voucher generation view")
        if not Package.objects.exists():
            logger.error("No packages found for voucher generation")
            messages.error(request, "No packages available. Please create a package first.")
            return redirect('admin:customers_package_changelist')
        
        form = GenerateVouchersForm(request.POST or None)
        if request.POST and form.is_valid():
            count = form.cleaned_data['count']
            length = form.cleaned_data['length']
            char_type = form.cleaned_data['char_type']
            prefix = form.cleaned_data['prefix']
            package = form.cleaned_data['package']
            
            logger.info(f"Generating {count} vouchers with length {length}, char_type {char_type}, prefix {prefix}, package {package.name}")
            try:
                codes = generate_voucher_codes(count, length, char_type, prefix)
                vouchers = []
                for code in codes:
                    voucher = Voucher.objects.create(
                        code=code,
                        prefix=prefix,
                        package=package,
                        is_active=True
                    )
                    vouchers.append(voucher)
                    router = package.router
                    if router.connection_type in ['API', 'VPN']:
                        try:
                            api = routeros_api.RouterOsApiPool(
                                router.ip_address, username=router.username,
                                password=router.password, port=router.api_port
                            ).get_api()
                            if package.connection_type == 'HOTSPOT':
                                api.get_resource('/ip/hotspot/user').add(
                                    name=code, password=code, profile=package.name,
                                    limit_uptime=f"{package.duration_days or 0}d"
                                )
                                logger.info(f"Synced voucher {code} to MikroTik Hotspot")
                            elif package.connection_type == 'PPPOE':
                                api.get_resource('/ppp/secret').add(
                                    name=code, password=code, service='pppoe',
                                    profile=package.name
                                )
                                logger.info(f"Synced voucher {code} to MikroTik PPPoE")
                            elif package.connection_type == 'STATIC':
                                api.get_resource('/ip/dhcp-server/lease').add(
                                    address=package.ip_address or '192.168.1.100',
                                    mac_address='',
                                    comment=f"Voucher {code}",
                                    server='all',
                                    lease_time=f"{package.duration_days or 30}d"
                                )
                                logger.info(f"Synced voucher {code} to MikroTik Static Lease")
                            elif package.connection_type == 'VPN':
                                api.get_resource('/ppp/secret').add(
                                    name=code, password=code, service='l2tp',
                                    profile=package.name
                                )
                                logger.info(f"Synced voucher {code} to MikroTik VPN")
                        except Exception as e:
                            logger.error(f"Failed to sync voucher {code} to MikroTik: {e}")
                            messages.warning(request, f"Failed to sync voucher {code} to MikroTik: {e}")
                    elif router.connection_type == 'RADIUS':
                        try:
                            db = MySQLdb.connect(
                                host=router.radius_server, user='radius_user',
                                passwd='radius_pass', db='radius'
                            )
                            cursor = db.cursor()
                            cursor.execute(
                                "INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                (code, 'Cleartext-Password', ':=', code)
                            )
                            if package.connection_type == 'STATIC':
                                cursor.execute(
                                    "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                    (code, 'Framed-IP-Address', ':=', package.ip_address or '192.168.1.100')
                                )
                            elif package.connection_type == 'VPN':
                                cursor.execute(
                                    "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                    (code, 'Service-Type', ':=', 'Framed-User')
                                )
                                cursor.execute(
                                    "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                    (code, 'Framed-Protocol', ':=', 'L2TP')
                                )
                            db.commit()
                            db.close()
                            logger.info(f"Synced voucher {code} to RADIUS")
                        except Exception as e:
                            logger.error(f"Failed to sync voucher {code} to RADIUS: {e}")
                            messages.warning(request, f"Failed to sync voucher {code} to RADIUS: {e}")
                
                messages.success(request, f"Generated {count} vouchers successfully")
                logger.info(f"Successfully generated {count} vouchers")
                return render(request, 'admin/voucher_results.html', {
                    'vouchers': vouchers,
                    'app_label': 'customers',
                    'opts': self.model._meta,
                })
            except Exception as e:
                logger.error(f"Failed to generate vouchers: {e}")
                messages.error(request, f"Failed to generate vouchers: {e}")
        
        logger.info("Rendering voucher generation form")
        return render(request, 'admin/generate_vouchers.html', {
            'form': form,
            'app_label': 'customers',
            'opts': self.model._meta,
        })

    def generate_vouchers(self, request, queryset):
        return self.generate_vouchers_view(request)