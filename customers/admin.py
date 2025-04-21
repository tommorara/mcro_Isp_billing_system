from django.contrib import admin
from django import forms
from django.urls import reverse, path
from django.utils.html import format_html
from django.shortcuts import redirect, render
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from .models import Customer, AuditLog, Location, Router, Package, Subscription, SessionLog, Invoice, Compensation, SupportTicket, Voucher
from .utils import generate_voucher_codes, send_sms
import routeros_api
import MySQLdb
import logging

logger = logging.getLogger(__name__)

class CustomerAdminForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = '__all__'
        help_texts = {
            'raw_phone': 'Enter phone without country code (e.g., 0712345678 for Kenya)',
        }

    def clean_raw_phone(self):
        raw_phone = self.cleaned_data['raw_phone']
        company = self.cleaned_data.get('company')
        if company:
            country = company.country
            digits = ''.join(filter(str.isdigit, raw_phone))
            if country == 'KE' and len(digits) != 10:
                raise forms.ValidationError("Kenyan numbers must have 10 digits (e.g., 0712345678).")
            elif country == 'US' and len(digits) != 10:
                raise forms.ValidationError("US numbers must have 10 digits (e.g., 1234567890).")
            elif country == 'UK' and len(digits) not in [10, 11]:
                raise forms.ValidationError("UK numbers must have 10 or 11 digits.")
        return raw_phone

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
    search_fields = ['name', 'email', 'raw_phone']
    list_filter = ['company', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (None, {
            'fields': (
                'company',
                'name',
                'email',
                'raw_phone',
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
    fieldsets = (
        (None, {
            'fields': ('company', 'location', 'name', 'connection_type', 'ip_address', 'username', 'password', 'api_port')
        }),
        ('RADIUS Settings', {
            'fields': ('radius_server', 'radius_secret'),
            'classes': ('collapse',),
        }),
        ('VPN Settings', {
            'fields': ('vpn_server', 'vpn_protocol', 'vpn_username', 'vpn_password', 'vpn_wg_private_key', 'vpn_wg_public_key', 'vpn_wg_endpoint_port'),
            'classes': ('collapse',),
        }),
    )

@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'connection_type', 'price_display', 'download_bandwidth', 'upload_bandwidth', 'data_limit', 'company', 'created_at']
    search_fields = ['name']
    list_filter = ['connection_type', 'company', 'location', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (None, {
            'fields': ('company', 'location', 'router', 'name', 'connection_type', 'price', 'ip_address')
        }),
        ('Duration', {
            'fields': ('duration_minutes', 'duration_hours', 'duration_days'),
            'classes': ('collapse',),
        }),
        ('Bandwidth and Data Settings', {
            'fields': ('download_bandwidth', 'upload_bandwidth', 'data_limit'),
            'classes': ('collapse',),
            'description': 'Configure bandwidth and data limit settings for the package. These are synced to MikroTik for HOTSPOT users.'
        }),
    )

    def price_display(self, obj):
        return obj.get_price_display()
    price_display.short_description = 'Price'

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
    list_display = ['customer', 'amount_display', 'status', 'issued_date', 'created_at', 'sales_report']
    search_fields = ['customer__name']
    list_filter = ['status', 'issued_date', 'created_at']
    readonly_fields = ['created_at', 'updated_at']

    def amount_display(self, obj):
        return obj.get_amount_display()
    amount_display.short_description = 'Amount'

    def sales_report(self, obj):
        return format_html(
            '<a href="{}">Daily Sales</a> | <a href="{}">Monthly Sales</a>',
            reverse('daily_sales_report'),
            reverse('monthly_sales_report')
        )
    sales_report.short_description = 'Sales Reports'

@admin.register(Compensation)
class CompensationAdmin(admin.ModelAdmin):
    list_display = ['customer', 'subscription', 'amount', 'duration_minutes', 'duration_hours', 'issued_date', 'created_at']
    search_fields = ['customer__name', 'reason']
    list_filter = ['issued_date', 'created_at']
    readonly_fields = ['issued_date', 'created_at', 'updated_at']

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['ticket_number', 'customer', 'subject', 'category', 'priority', 'status', 'assigned_to', 'is_admin_reply', 'created_at']
    search_fields = ['ticket_number', 'subject', 'message', 'customer__name', 'customer__email']
    list_filter = ['category', 'priority', 'status', 'is_admin_reply', 'created_at']
    readonly_fields = ['ticket_number', 'created_at', 'updated_at']
    actions = ['mark_in_progress', 'mark_closed']
    list_editable = ['assigned_to']

    def mark_in_progress(self, request, queryset):
        for ticket in queryset:
            if ticket.status != 'IN_PROGRESS':
                ticket.status = 'IN_PROGRESS'
                ticket.save()
                AuditLog.objects.create(
                    action='Status Changed',
                    model='SupportTicket',
                    object_id=ticket.id,
                    user=request.user,
                )
                send_sms(ticket.customer.phone, f"Your ticket #{ticket.ticket_number} is now in progress.")
                send_email(
                    ticket.customer.email,
                    f"Ticket #{ticket.ticket_number} Status Update",
                    f"Your ticket '{ticket.subject}' is now In Progress."
                )
        self.message_user(request, "Selected tickets marked as In Progress.")
    mark_in_progress.short_description = "Mark as In Progress"

    def mark_closed(self, request, queryset):
        for ticket in queryset:
            if ticket.status != 'CLOSED':
                ticket.status = 'CLOSED'
                ticket.save()
                AuditLog.objects.create(
                    action='Status Changed',
                    model='SupportTicket',
                    object_id=ticket.id,
                    user=request.user,
                )
                send_sms(ticket.customer.phone, f"Your ticket #{ticket.ticket_number} has been closed.")
                send_email(
                    ticket.customer.email,
                    f"Ticket #{ticket.ticket_number} Closed",
                    f"Your ticket '{ticket.subject}' has been closed. Thank you for your feedback."
                )
        self.message_user(request, "Selected tickets marked as Closed.")
    mark_closed.short_description = "Mark as Closed"

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
                            rate_limit = f"{package.upload_bandwidth}k/{package.download_bandwidth}k" if package.download_bandwidth and package.upload_bandwidth else ""
                            data_limit_bytes = package.data_limit * 1024 * 1024 if package.data_limit else None
                            if package.connection_type == 'HOTSPOT':
                                params = {
                                    'name': code,
                                    'password': code,
                                    'profile': package.name,
                                    'limit-uptime': f"{package.duration_days or 0}d"
                                }
                                if rate_limit:
                                    params['rate-limit'] = rate_limit
                                if data_limit_bytes:
                                    params['limit-bytes-total'] = str(data_limit_bytes)
                                api.get_resource('/ip/hotspot/user').add(**params)
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
                                passwd=router.radius_secret, db='radius'
                            )
                            cursor = db.cursor()
                            cursor.execute(
                                "INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                (code, 'Cleartext-Password', ':=', code)
                            )
                            if data_limit_bytes:
                                cursor.execute(
                                    "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                    (code, 'Mikrotik-Total-Limit', ':=', str(data_limit_bytes))
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