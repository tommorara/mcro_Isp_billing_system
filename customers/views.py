from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate, TruncMonth
from datetime import timedelta, datetime
from .models import Customer, Package, Subscription, Invoice, SupportTicket, Voucher, Compensation, AuditLog
from .utils import send_sms, send_email
from payments.models import Payment
from plugins.models import PluginConfig
from plugins.base import PaymentPlugin
from functools import wraps
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import serializers
import json
import logging
import routeros_api
import MySQLdb
import subprocess
import os

logger = logging.getLogger(__name__)

class PackageSerializer(serializers.ModelSerializer):
    price_display = serializers.CharField(source='get_price_display')

    class Meta:
        model = Package
        fields = ['id', 'name', 'connection_type', 'price_display', 'duration_minutes', 'duration_hours', 'duration_days', 'data_limit']

@api_view(['GET'])
def hotspot_plans_api(request):
    packages = Package.objects.filter(connection_type='HOTSPOT')
    serializer = PackageSerializer(packages, many=True)
    return Response(serializer.data)

def connect_to_router(router):
    """Utility to connect to MikroTik router via API, VPN, or RADIUS."""
    if router.connection_type == 'API':
        return routeros_api.RouterOsApiPool(
            router.ip_address, username=router.username,
            password=router.password, port=router.api_port
        ).get_api()
    elif router.connection_type == 'VPN':
        try:
            if router.vpn_protocol == 'L2TP':
                logger.info(f"Connecting to router {router.name} via L2TP")
                return routeros_api.RouterOsApiPool(
                    router.ip_address, username=router.username,
                    password=router.password, port=router.api_port
                ).get_api()
            elif router.vpn_protocol == 'OPENVPN':
                vpn_dir = os.path.join(os.getcwd(), 'vpn_configs')
                os.makedirs(vpn_dir, exist_ok=True)
                cred_file = os.path.join(vpn_dir, f"{router.id}.txt")
                with open(cred_file, 'w') as f:
                    f.write(f"{router.vpn_username}\n{router.vpn_password}")
                ovpn_file = os.path.join(vpn_dir, f"{router.id}.ovpn")
                with open(ovpn_file, 'w') as f:
                    f.write(f"# OpenVPN config for {router.name}\n")
                    f.write(f"client\n")
                    f.write(f"dev tun\n")
                    f.write(f"proto tcp\n")
                    f.write(f"remote {router.vpn_server} 1194\n")
                    f.write(f"auth-user-pass {cred_file}\n")
                subprocess.run([
                    'openvpn', '--config', ovpn_file,
                    '--auth-user-pass', cred_file,
                    '--daemon'
                ], check=True)
                logger.info(f"Started OpenVPN for router {router.name}")
                return routeros_api.RouterOsApiPool(
                    router.ip_address, username=router.username,
                    password=router.password, port=router.api_port
                ).get_api()
            elif router.vpn_protocol == 'WIREGUARD':
                wg_dir = os.path.join(os.getcwd(), 'wg_configs')
                os.makedirs(wg_dir, exist_ok=True)
                wg_conf = os.path.join(wg_dir, f"wg_{router.id}.conf")
                with open(wg_conf, 'w') as f:
                    f.write(f"[Interface]\n")
                    f.write(f"PrivateKey = {router.vpn_wg_private_key}\n")
                    f.write(f"Address = 10.0.0.2/24\n")
                    f.write(f"[Peer]\n")
                    f.write(f"PublicKey = {router.vpn_wg_public_key}\n")
                    f.write(f"Endpoint = {router.vpn_server}:{router.vpn_wg_endpoint_port}\n")
                    f.write(f"AllowedIPs = 0.0.0.0/0\n")
                subprocess.run(['wg-quick', 'up', wg_conf], check=True)
                logger.info(f"Started WireGuard for router {router.name}")
                return routeros_api.RouterOsApiPool(
                    router.ip_address, username=router.username,
                    password=router.password, port=router.api_port
                ).get_api()
            elif router.vpn_protocol == 'PPTP':
                logger.info(f"Connecting to router {router.name} via PPTP")
                return routeros_api.RouterOsApiPool(
                    router.ip_address, username=router.username,
                    password=router.password, port=router.api_port
                ).get_api()
            else:
                raise ValueError(f"Unsupported VPN protocol: {router.vpn_protocol}")
        except Exception as e:
            logger.error(f"VPN connection failed for {router.name}: {e}")
            raise
    elif router.connection_type == 'RADIUS':
        return None
    raise ValueError(f"Unsupported connection type: {router.connection_type}")

def get_rate_limit(package):
    """Generate MikroTik rate-limit string for bandwidth settings."""
    if package.download_bandwidth and package.upload_bandwidth:
        return f"{package.upload_bandwidth}k/{package.download_bandwidth}k"
    return ""

@api_view(['GET', 'POST'])
def hotspot_pay_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            package_id = data.get('package_id')
            raw_phone = data.get('phone')
            voucher_code = data.get('voucher_code')
            
            if not package_id or not raw_phone:
                return Response({'error': 'Package ID and phone number are required'}, status=400)
            
            package = get_object_or_404(Package, id=package_id, connection_type__in=['HOTSPOT', 'PPPOE', 'STATIC', 'VPN'])
            customer, created = Customer.objects.get_or_create(
                email=f"{package.connection_type.lower()}_{raw_phone}@example.com".lower(),
                defaults={
                    'company': package.company,
                    'name': f"{package.connection_type} User {raw_phone}",
                    'raw_phone': raw_phone,
                    'password': make_password('user123')
                }
            )
            if created:
                send_sms(customer.phone, f"Welcome to {package.company.name}! Your account has been created.")
                send_email(
                    customer.email,
                    f"Welcome to {package.company.name}",
                    f"Dear {customer.name},\n\nYour account has been created. Log in at {request.build_absolute_uri('/customer/login/')}.\n\nBest,\n{package.company.name}"
                )
            
            if voucher_code:
                try:
                    voucher = Voucher.objects.get(code__iexact=voucher_code, is_active=True, redeemed_at__isnull=True)
                    if voucher.package != package:
                        return Response({'error': 'Voucher not valid for this package'}, status=400)
                    duration = (
                        timedelta(minutes=package.duration_minutes or 0) +
                        timedelta(hours=package.duration_hours or 0) +
                        timedelta(days=package.duration_days or 0)
                    )
                    username = voucher.code if package.connection_type == 'HOTSPOT' and package.company.hotspot_login_method == 'VOUCHER' else f"{package.connection_type.lower()}_{raw_phone}_{timezone.now().strftime('%Y%m%d%H%M%S')}"
                    subscription = Subscription.objects.create(
                        customer=customer,
                        package=package,
                        connection_type=package.connection_type,
                        username=username,
                        password='user123',
                        start_date=timezone.now(),
                        end_date=timezone.now() + duration,
                        router=package.router,
                        is_active=True
                    )
                    voucher.redeemed_at = timezone.now()
                    voucher.is_active = False
                    voucher.save()
                    
                    router = package.router
                    data_limit_bytes = package.data_limit * 1024 * 1024 if package.data_limit else None
                    if router.connection_type in ['API', 'VPN']:
                        try:
                            api = connect_to_router(router)
                            if package.connection_type == 'HOTSPOT':
                                params = {
                                    'name': username,
                                    'password': 'user123',
                                    'profile': package.name,
                                    'limit-uptime': f"{package.duration_days or 0}d",
                                    'comment': f"Created={timezone.now():%b/%d/%Y %H:%M:%S} Expire={(timezone.now() + duration):%b/%d/%Y %H:%M:%S}"
                                }
                                rate_limit = get_rate_limit(package)
                                if rate_limit:
                                    params['rate-limit'] = rate_limit
                                if data_limit_bytes:
                                    params['limit-bytes-total'] = str(data_limit_bytes)
                                api.get_resource('/ip/hotspot/user').add(**params)
                            elif package.connection_type == 'PPPOE':
                                api.get_resource('/ppp/secret').add(
                                    name=username, password='user123', service='pppoe',
                                    profile=package.name
                                )
                            elif package.connection_type == 'STATIC':
                                api.get_resource('/ip/dhcp-server/lease').add(
                                    address=package.ip_address or '192.168.1.100',
                                    mac_address='',
                                    comment=f"Subscription {username}",
                                    server='all',
                                    lease_time=f"{package.duration_days or 30}d"
                                )
                            elif package.connection_type == 'VPN':
                                api.get_resource('/ppp/secret').add(
                                    name=username, password='user123', service='l2tp',
                                    profile=package.name
                                )
                            logger.info(f"Synced {username} to MikroTik for {package.connection_type}")
                        except Exception as e:
                            logger.error(f"Failed to sync {username} to MikroTik: {e}")
                    elif router.connection_type == 'RADIUS':
                        try:
                            db = MySQLdb.connect(
                                host=router.radius_server, user='radius_user',
                                passwd=router.radius_secret, db='radius'
                            )
                            cursor = db.cursor()
                            cursor.execute(
                                "INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                (username, 'Cleartext-Password', ':=', 'user123')
                            )
                            if data_limit_bytes:
                                cursor.execute(
                                    "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                    (username, 'Mikrotik-Total-Limit', ':=', str(data_limit_bytes))
                                )
                            if package.connection_type == 'STATIC':
                                cursor.execute(
                                    "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                    (username, 'Framed-IP-Address', ':=', package.ip_address or '192.168.1.100')
                                )
                            elif package.connection_type == 'VPN':
                                cursor.execute(
                                    "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                    (username, 'Service-Type', ':=', 'Framed-User')
                                )
                                cursor.execute(
                                    "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                    (username, 'Framed-Protocol', ':=', 'L2TP')
                                )
                            db.commit()
                            db.close()
                            logger.info(f"Synced {username} to RADIUS for {package.connection_type}")
                        except Exception as e:
                            logger.error(f"Failed to sync {username} to RADIUS: {e}")
                    
                    send_sms(customer.phone, f"Voucher redeemed! Username: {subscription.username}, Password: {subscription.password}")
                    send_email(
                        customer.email,
                        f"Voucher Redeemed for {package.name}",
                        f"Dear {customer.name},\n\nYour voucher has been redeemed. Username: {subscription.username}, Password: {subscription.password}\n\nBest,\n{package.company.name}"
                    )
                    return Response({
                        'status': 'success',
                        'username': subscription.username,
                        'password': subscription.password,
                        'login_method': package.company.hotspot_login_method
                    })
                except Voucher.DoesNotExist:
                    return Response({'error': 'Invalid or already used voucher'}, status=400)
            
            payment_plugin = PluginConfig.objects.filter(plugin_type='PAYMENT', is_active=True).first()
            if not payment_plugin:
                return Response({'error': 'No active payment plugin configured'}, status=400)
            
            plugin = PaymentPlugin.load(payment_plugin)
            invoice = Invoice.objects.create(
                customer=customer,
                subscription=None,
                amount=package.price,
                status='PENDING'
            )
            payment = Payment.objects.create(
                customer=customer,
                invoice=invoice,
                amount=package.price,
                transaction_id=f"{package.connection_type}-{invoice.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                payment_method=payment_plugin.name,
                status='PENDING'
            )
            
            response = plugin.initiate_payment(package.price, customer.phone, invoice.id, customer.id)
            if response.get('ResponseCode') == '0':
                payment.transaction_id = response.get('CheckoutRequestID')
                payment.save()
                send_sms(customer.phone, f"Payment initiated for {package.name}. Transaction ID: {payment.transaction_id}")
                send_email(
                    customer.email,
                    f"Payment Initiated for {package.name}",
                    f"Dear {customer.name},\n\nPayment initiated for {package.name}. Transaction ID: {payment.transaction_id}\n\nBest,\n{package.company.name}"
                )
                return Response({
                    'status': 'pending',
                    'transaction_id': payment.transaction_id,
                    'message': 'Please complete the payment'
                })
            else:
                payment.status = 'FAILED'
                invoice.status = 'FAILED'
                payment.save()
                invoice.save()
                send_sms(customer.phone, f"Payment failed for {package.name}. Please try again.")
                send_email(
                    customer.email,
                    f"Payment Failed for {package.name}",
                    f"Dear {customer.name},\n\nPayment failed for {package.name}. Please try again.\n\nBest,\n{package.company.name}"
                )
                return Response({'error': 'Failed to initiate payment'}, status=400)
        
        except Exception as e:
            logger.error(f"Payment error for {package.connection_type}: {e}")
            return Response({'error': str(e)}, status=500)
    
    elif request.method == 'GET':
        transaction_id = request.GET.get('transaction_id')
        if not transaction_id:
            return Response({'error': 'Transaction ID required'}, status=400)
        
        try:
            payment = Payment.objects.get(transaction_id=transaction_id)
            if payment.status == 'SUCCESS':
                subscription = payment.invoice.subscription
                if not subscription:
                    package = payment.invoice.customer.subscription_set.last().package
                    duration = (
                        timedelta(minutes=package.duration_minutes or 0) +
                        timedelta(hours=package.duration_hours or 0) +
                        timedelta(days=package.duration_days or 0)
                    )
                    username = f"{package.connection_type.lower()}_{payment.customer.raw_phone}_{timezone.now().strftime('%Y%m%d%H%M%S')}"
                    subscription = Subscription.objects.create(
                        customer=payment.customer,
                        package=package,
                        connection_type=package.connection_type,
                        username=username,
                        password='user123',
                        start_date=timezone.now(),
                        end_date=timezone.now() + duration,
                        router=package.router,
                        is_active=True
                    )
                    payment.invoice.subscription = subscription
                    payment.invoice.save()
                    
                    router = package.router
                    data_limit_bytes = package.data_limit * 1024 * 1024 if package.data_limit else None
                    if router.connection_type in ['API', 'VPN']:
                        try:
                            api = connect_to_router(router)
                            if package.connection_type == 'HOTSPOT':
                                params = {
                                    'name': username,
                                    'password': 'user123',
                                    'profile': package.name,
                                    'limit-uptime': f"{package.duration_days or 0}d",
                                    'comment': f"Created={timezone.now():%b/%d/%Y %H:%M:%S} Expire={(timezone.now() + duration):%b/%d/%Y %H:%M:%S}"
                                }
                                rate_limit = get_rate_limit(package)
                                if rate_limit:
                                    params['rate-limit'] = rate_limit
                                if data_limit_bytes:
                                    params['limit-bytes-total'] = str(data_limit_bytes)
                                api.get_resource('/ip/hotspot/user').add(**params)
                            elif package.connection_type == 'PPPOE':
                                api.get_resource('/ppp/secret').add(
                                    name=username, password='user123', service='pppoe',
                                    profile=package.name
                                )
                            elif package.connection_type == 'STATIC':
                                api.get_resource('/ip/dhcp-server/lease').add(
                                    address=package.ip_address or '192.168.1.100',
                                    mac_address='',
                                    comment=f"Subscription {username}",
                                    server='all',
                                    lease_time=f"{package.duration_days or 30}d"
                                )
                            elif package.connection_type == 'VPN':
                                api.get_resource('/ppp/secret').add(
                                    name=username, password='user123', service='l2tp',
                                    profile=package.name
                                )
                            logger.info(f"Synced {username} to MikroTik for {package.connection_type}")
                        except Exception as e:
                            logger.error(f"Failed to sync {username} to MikroTik: {e}")
                    elif router.connection_type == 'RADIUS':
                        try:
                            db = MySQLdb.connect(
                                host=router.radius_server, user='radius_user',
                                passwd=router.radius_secret, db='radius'
                            )
                            cursor = db.cursor()
                            cursor.execute(
                                "INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                (username, 'Cleartext-Password', ':=', 'user123')
                            )
                            if data_limit_bytes:
                                cursor.execute(
                                    "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                    (username, 'Mikrotik-Total-Limit', ':=', str(data_limit_bytes))
                                )
                            if package.connection_type == 'STATIC':
                                cursor.execute(
                                    "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                    (username, 'Framed-IP-Address', ':=', package.ip_address or '192.168.1.100')
                                )
                            elif package.connection_type == 'VPN':
                                cursor.execute(
                                    "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                    (username, 'Service-Type', ':=', 'Framed-User')
                                )
                                cursor.execute(
                                    "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                    (username, 'Framed-Protocol', ':=', 'L2TP')
                                )
                            db.commit()
                            db.close()
                            logger.info(f"Synced {username} to RADIUS for {package.connection_type}")
                        except Exception as e:
                            logger.error(f"Failed to sync {username} to RADIUS: {e}")
                
                send_sms(payment.customer.phone, f"Payment successful! Username: {subscription.username}, Password: {subscription.password}")
                send_email(
                    payment.customer.email,
                    f"Payment Successful for {subscription.package.name}",
                    f"Dear {payment.customer.name},\n\nPayment successful! Username: {subscription.username}, Password: {subscription.password}\n\nBest,\n{subscription.package.company.name}"
                )
                return Response({
                    'status': 'success',
                    'username': subscription.username,
                    'password': subscription.password,
                    'login_method': subscription.package.company.hotspot_login_method
                })
            elif payment.status == 'FAILED':
                return Response({'status': 'failed', 'error': 'Payment failed'})
            else:
                return Response({'status': 'pending'})
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=404)

def customer_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'customer_id' not in request.session:
            messages.error(request, 'Please log in to access this page.')
            return redirect('customer_login')
        return view_func(request, *args, **kwargs)
    return wrapper

def customer_login(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        try:
            customer = Customer.objects.get(email=email)
            if check_password(password, customer.password):
                request.session['customer_id'] = customer.id
                logger.info(f"Customer {email} logged in successfully")
                send_sms(customer.phone, f"You have logged in to your {customer.company.name} account.")
                send_email(
                    customer.email,
                    f"Login to {customer.company.name}",
                    f"Dear {customer.name},\n\nYou have successfully logged in.\n\nBest,\n{customer.company.name}"
                )
                messages.success(request, 'Logged in successfully.')
                return redirect('customer_dashboard')
            else:
                logger.warning(f"Invalid password for {email}")
                messages.error(request, 'Invalid email or password.')
        except Customer.DoesNotExist:
            logger.warning(f"Customer with email {email} not found")
            messages.error(request, 'Invalid email or password.')
    return render(request, 'customers/login.html')

def customer_logout(request):
    customer = Customer.objects.get(id=request.session.get('customer_id'))
    request.session.flush()
    send_sms(customer.phone, f"You have logged out of your {customer.company.name} account.")
    send_email(
        customer.email,
        f"Logout from {customer.company.name}",
        f"Dear {customer.name},\n\nYou have successfully logged out.\n\nBest,\n{customer.company.name}"
    )
    messages.success(request, 'Logged out successfully.')
    return redirect('customer_login')

@customer_required
def customer_dashboard(request):
    customer = Customer.objects.get(id=request.session['customer_id'])
    subscriptions = Subscription.objects.filter(customer=customer)
    invoices = Invoice.objects.filter(customer=customer)
    tickets = SupportTicket.objects.filter(customer=customer, parent__isnull=True, is_admin_reply=False)
    vouchers = Voucher.objects.filter(package__company=customer.company, is_active=True)
    return render(request, 'customers/dashboard.html', {
        'customer': customer,
        'subscriptions': subscriptions,
        'invoices': invoices,
        'tickets': tickets,
        'vouchers': vouchers,
    })

@customer_required
def customer_profile(request):
    customer = Customer.objects.get(id=request.session['customer_id'])
    compensations = Compensation.objects.filter(customer=customer)
    if request.method == 'POST':
        customer.name = request.POST.get('name')
        customer.email = request.POST.get('email', '').lower()
        customer.raw_phone = request.POST.get('raw_phone')
        customer.address = request.POST.get('address')
        password = request.POST.get('password')
        if password:
            customer.password = make_password(password)
        customer.save()
        send_sms(customer.phone, "Your profile has been updated successfully.")
        send_email(
            customer.email,
            f"Profile Updated at {customer.company.name}",
            f"Dear {customer.name},\n\nYour profile has been updated successfully.\n\nBest,\n{customer.company.name}"
        )
        messages.success(request, 'Profile updated successfully.')
        return redirect('customer_profile')
    return render(request, 'customers/profile.html', {
        'customer': customer,
        'compensations': compensations,
    })

@customer_required
def customer_packages(request):
    customer = Customer.objects.get(id=request.session['customer_id'])
    connection_type = request.GET.get('connection_type')
    router_id = request.GET.get('router_id')
    location_id = request.GET.get('location_id')
    packages = Package.objects.filter(company=customer.company)
    if connection_type:
        packages = packages.filter(connection_type=connection_type)
    if router_id:
        packages = packages.filter(router_id=router_id)
    if location_id:
        packages = packages.filter(location_id=location_id)
    return render(request, 'customers/packages.html', {
        'packages': packages,
        'customer': customer,
    })

@customer_required
def customer_purchase(request, package_id):
    customer = Customer.objects.get(id=request.session['customer_id'])
    package = get_object_or_404(Package, id=package_id, company=customer.company)
    if request.method == 'POST':
        invoice = Invoice.objects.create(
            customer=customer,
            subscription=None,
            amount=package.price,
            status='PENDING'
        )
        send_sms(customer.phone, f"Purchase initiated for {package.name}. Invoice ID: {invoice.id}")
        send_email(
            customer.email,
            f"Purchase Initiated for {package.name}",
            f"Dear {customer.name},\n\nPurchase initiated for {package.name}. Invoice ID: {invoice.id}\n\nBest,\n{package.company.name}"
        )
        return redirect('select_payment_method', invoice_id=invoice.id)
    return render(request, 'customers/purchase.html', {
        'package': package,
        'customer': customer,
    })

@customer_required
def customer_plans(request):
    customer = Customer.objects.get(id=request.session['customer_id'])
    subscriptions = Subscription.objects.filter(customer=customer)
    return render(request, 'customers/plans.html', {
        'subscriptions': subscriptions,
        'customer': customer,
    })

@customer_required
def customer_invoices(request):
    customer = Customer.objects.get(id=request.session['customer_id'])
    invoices = Invoice.objects.filter(customer=customer).order_by('-issued_date')
    return render(request, 'customers/invoices.html', {
        'invoices': invoices,
        'customer': customer,
    })

@customer_required
def customer_tickets(request):
    customer = Customer.objects.get(id=request.session['customer_id'])
    tickets = SupportTicket.objects.filter(customer=customer, parent__isnull=True, is_admin_reply=False).order_by('-created_at')
    if request.method == 'POST':
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        category = request.POST.get('category')
        priority = request.POST.get('priority')
        attachment = request.FILES.get('attachment')
        ticket = SupportTicket.objects.create(
            customer=customer,
            subject=subject,
            message=message,
            category=category,
            priority=priority,
            attachment=attachment,
            status='OPEN',
            is_admin_reply=False
        )
        AuditLog.objects.create(
            action='Ticket Created',
            model='SupportTicket',
            object_id=ticket.id,
            user=None,  # Customer action
        )
        send_sms(customer.phone, f"Support ticket #{ticket.ticket_number} created: {subject}")
        send_email(
            customer.email,
            f"Support Ticket #{ticket.ticket_number} Created",
            f"Dear {customer.name},\n\nYour ticket '{subject}' has been created.\n\nBest,\n{customer.company.name}"
        )
        send_email(
            customer.company.email,
            f"New Support Ticket #{ticket.ticket_number}",
            f"A new ticket '{subject}' has been created by {customer.name}.\n\nMessage: {message}\n\nView at {request.build_absolute_uri('/admin/customers/supportticket/')}"
        )
        if ticket.priority == 'HIGH':
            for admin in User.objects.filter(is_staff=True):
                send_email(
                    admin.email,
                    f"Urgent: High-Priority Ticket #{ticket.ticket_number}",
                    f"High-priority ticket '{subject}' by {customer.name} requires immediate attention.\n\nMessage: {message}\n\nView at {request.build_absolute_uri('/admin/customers/supportticket/')}"
                )
        messages.success(request, f'Ticket #{ticket.ticket_number} created successfully.')
        return redirect('customer_tickets')
    return render(request, 'customers/tickets.html', {
        'tickets': tickets,
        'customer': customer,
    })

@customer_required
def customer_ticket_detail(request, ticket_id):
    customer = Customer.objects.get(id=request.session['customer_id'])
    ticket = get_object_or_404(SupportTicket, id=ticket_id, customer=customer, parent__isnull=True, is_admin_reply=False)
    replies = SupportTicket.objects.filter(parent=ticket).order_by('created_at')
    if request.method == 'POST':
        message = request.POST.get('message')
        attachment = request.FILES.get('attachment')
        reply = SupportTicket.objects.create(
            customer=customer,
            subject=f"Re: {ticket.subject}",
            message=message,
            category=ticket.category,
            priority=ticket.priority,
            attachment=attachment,
            status=ticket.status,
            is_admin_reply=False,
            parent=ticket
        )
        ticket.status = 'OPEN'
        ticket.save()
        AuditLog.objects.create(
            action='Reply Added',
            model='SupportTicket',
            object_id=reply.id,
            user=None,  # Customer action
        )
        send_sms(customer.phone, f"Reply added to ticket #{ticket.ticket_number}: {ticket.subject}")
        send_email(
            customer.email,
            f"Reply Added to Ticket #{ticket.ticket_number}",
            f"Dear {customer.name},\n\nYour reply to '{ticket.subject}' has been received.\n\nBest,\n{customer.company.name}"
        )
        send_email(
            customer.company.email,
            f"New Reply to Ticket #{ticket.ticket_number}",
            f"{customer.name} replied to '{ticket.subject}'.\n\nMessage: {message}\n\nView at {request.build_absolute_uri('/admin/customers/supportticket/')}"
        )
        if ticket.priority == 'HIGH':
            for admin in User.objects.filter(is_staff=True):
                send_email(
                    admin.email,
                    f"Urgent: Reply to High-Priority Ticket #{ticket.ticket_number}",
                    f"{customer.name} replied to high-priority ticket '{ticket.subject}'.\n\nMessage: {message}\n\nView at {request.build_absolute_uri('/admin/customers/supportticket/')}"
                )
        messages.success(request, 'Reply sent successfully.')
        return redirect('customer_ticket_detail', ticket_id=ticket.id)
    return render(request, 'customers/ticket_detail.html', {
        'ticket': ticket,
        'replies': replies,
        'customer': customer,
    })

@customer_required
def customer_renew(request, subscription_id):
    customer = Customer.objects.get(id=request.session['customer_id'])
    subscription = get_object_or_404(Subscription, id=subscription_id, customer=customer)
    if request.method == 'POST':
        package_id = request.POST.get('package_id')
        package = get_object_or_404(Package, id=package_id)
        invoice = Invoice.objects.create(
            customer=customer,
            subscription=subscription,
            amount=package.price,
            status='PENDING'
        )
        send_sms(customer.phone, f"Renewal initiated for {subscription.package.name}. Invoice ID: {invoice.id}")
        send_email(
            customer.email,
            f"Renewal Initiated for {subscription.package.name}",
            f"Dear {customer.name},\n\nRenewal initiated for {subscription.package.name}. Invoice ID: {invoice.id}\n\nBest,\n{package.company.name}"
        )
        return redirect('select_payment_method', invoice_id=invoice.id)
    packages = Package.objects.filter(connection_type=subscription.connection_type, router=subscription.router)
    return render(request, 'customers/renew.html', {
        'subscription': subscription,
        'packages': packages,
        'customer': customer,
    })

@customer_required
def recharge_subscription(request, subscription_id):
    customer = Customer.objects.get(id=request.session['customer_id'])
    subscription = get_object_or_404(Subscription, id=subscription_id, customer=customer)
    if request.method == 'POST':
        package_id = request.POST.get('package_id')
        package = get_object_or_404(Package, id=package_id)
        invoice = Invoice.objects.create(
            customer=customer,
            subscription=subscription,
            amount=package.price,
            status='PENDING'
        )
        send_sms(customer.phone, f"Recharge initiated for {subscription.package.name}. Invoice ID: {invoice.id}")
        send_email(
            customer.email,
            f"Recharge Initiated for {subscription.package.name}",
            f"Dear {customer.name},\n\nRecharge initiated for {subscription.package.name}. Invoice ID: {invoice.id}\n\nBest,\n{package.company.name}"
        )
        return redirect('select_payment_method', invoice_id=invoice.id)
    packages = Package.objects.filter(connection_type=subscription.connection_type, router=subscription.router)
    return render(request, 'customers/recharge.html', {
        'subscription': subscription,
        'packages': packages,
        'customer': customer,
    })

@customer_required
def redeem_voucher(request):
    customer = Customer.objects.get(id=request.session['customer_id'])
    if request.method == 'POST':
        code = request.POST.get('code')
        try:
            voucher = Voucher.objects.get(code__iexact=code, is_active=True, redeemed_at__isnull=True)
            package = voucher.package
            duration = (
                timedelta(minutes=package.duration_minutes or 0) +
                timedelta(hours=package.duration_hours or 0) +
                timedelta(days=package.duration_days or 0)
            )
            username = voucher.code if package.connection_type == 'HOTSPOT' and package.company.hotspot_login_method == 'VOUCHER' else f"{package.connection_type.lower()}_{customer.raw_phone}_{timezone.now().strftime('%Y%m%d%H%M%S')}"
            subscription = Subscription.objects.create(
                customer=customer,
                package=package,
                connection_type=package.connection_type,
                username=username,
                password='user123',
                start_date=timezone.now(),
                end_date=timezone.now() + duration,
                router=package.router,
                is_active=True
            )
            voucher.redeemed_at = timezone.now()
            voucher.is_active = False
            voucher.save()
            
            router = package.router
            data_limit_bytes = package.data_limit * 1024 * 1024 if package.data_limit else None
            if router.connection_type in ['API', 'VPN']:
                try:
                    api = connect_to_router(router)
                    if package.connection_type == 'HOTSPOT':
                        params = {
                            'name': username,
                            'password': 'user123',
                            'profile': package.name,
                            'limit-uptime': f"{package.duration_days or 0}d",
                            'comment': f"Created={timezone.now():%b/%d/%Y %H:%M:%S} Expire={(timezone.now() + duration):%b/%d/%Y %H:%M:%S}"
                        }
                        rate_limit = get_rate_limit(package)
                        if rate_limit:
                            params['rate-limit'] = rate_limit
                        if data_limit_bytes:
                            params['limit-bytes-total'] = str(data_limit_bytes)
                        api.get_resource('/ip/hotspot/user').add(**params)
                    elif package.connection_type == 'PPPOE':
                        api.get_resource('/ppp/secret').add(
                            name=username, password='user123', service='pppoe',
                            profile=package.name
                        )
                    elif package.connection_type == 'STATIC':
                        api.get_resource('/ip/dhcp-server/lease').add(
                            address=package.ip_address or '192.168.1.100',
                            mac_address='',
                            comment=f"Subscription {username}",
                            server='all',
                            lease_time=f"{package.duration_days or 30}d"
                        )
                    elif package.connection_type == 'VPN':
                        api.get_resource('/ppp/secret').add(
                            name=username, password='user123', service='l2tp',
                            profile=package.name
                        )
                    logger.info(f"Synced {username} to MikroTik for {package.connection_type}")
                except Exception as e:
                    logger.error(f"Failed to sync {username} to MikroTik: {e}")
            elif router.connection_type == 'RADIUS':
                try:
                    db = MySQLdb.connect(
                        host=router.radius_server, user='radius_user',
                        passwd=router.radius_secret, db='radius'
                    )
                    cursor = db.cursor()
                    cursor.execute(
                        "INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                        (username, 'Cleartext-Password', ':=', 'user123')
                    )
                    if data_limit_bytes:
                        cursor.execute(
                            "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                        (username, 'Mikrotik-Total-Limit', ':=', str(data_limit_bytes))
                    )
                    if package.connection_type == 'STATIC':
                        cursor.execute(
                            "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                            (username, 'Framed-IP-Address', ':=', package.ip_address or '192.168.1.100')
                        )
                    elif package.connection_type == 'VPN':
                        cursor.execute(
                            "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                            (username, 'Service-Type', ':=', 'Framed-User')
                        )
                        cursor.execute(
                            "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                            (username, 'Framed-Protocol', ':=', 'L2TP')
                        )
                    db.commit()
                    db.close()
                    logger.info(f"Synced {username} to RADIUS for {package.connection_type}")
                except Exception as e:
                    logger.error(f"Failed to sync {username} to RADIUS: {e}")
            
            send_sms(customer.phone, f"Voucher redeemed! Username: {subscription.username}, Password: {subscription.password}")
            send_email(
                customer.email,
                f"Voucher Redeemed for {package.name}",
                f"Dear {customer.name},\n\nYour voucher has been redeemed. Username: {subscription.username}, Password: {subscription.password}\n\nBest,\n{package.company.name}"
            )
            messages.success(request, 'Voucher redeemed successfully.')
            return redirect('customer_dashboard')
        except Voucher.DoesNotExist:
            messages.error(request, 'Invalid or already used voucher.')
            return redirect('redeem_voucher')
    return render(request, 'customers/redeem_voucher.html', {
        'customer': customer,
    })

@customer_required
def select_payment_method(request, invoice_id):
    customer = Customer.objects.get(id=request.session['customer_id'])
    invoice = get_object_or_404(Invoice, id=invoice_id, customer=customer)
    payment_plugins = PluginConfig.objects.filter(plugin_type='PAYMENT', is_active=True)
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        payment_plugin = PluginConfig.objects.filter(name=payment_method, plugin_type='PAYMENT', is_active=True).first()
        if not payment_plugin:
            messages.error(request, 'Invalid payment method selected.')
            return redirect('select_payment_method', invoice_id=invoice.id)
        
        plugin = PaymentPlugin.load(payment_plugin)
        response = plugin.initiate_payment(invoice.amount, customer.phone, invoice.id, customer.id)
        if response.get('ResponseCode') == '0':
            payment = Payment.objects.create(
                customer=customer,
                invoice=invoice,
                amount=invoice.amount,
                transaction_id=response.get('CheckoutRequestID'),
                payment_method=payment_plugin.name,
                status='PENDING'
            )
            send_sms(customer.phone, f"Payment initiated for Invoice #{invoice.id}. Transaction ID: {payment.transaction_id}")
            send_email(
                customer.email,
                f"Payment Initiated for Invoice #{invoice.id}",
                f"Dear {customer.name},\n\nPayment initiated for Invoice #{invoice.id}. Transaction ID: {payment.transaction_id}\n\nBest,\n{customer.company.name}"
            )
            return redirect('hotspot_pay_api', transaction_id=payment.transaction_id)
        else:
            messages.error(request, 'Failed to initiate payment. Please try again.')
            return redirect('select_payment_method', invoice_id=invoice.id)
    return render(request, 'customers/select_payment_method.html', {
        'customer': customer,
        'invoice': invoice,
        'payment_plugins': payment_plugins,
    })

@user_passes_test(lambda u: u.is_staff)
def daily_sales_report(request):
    sales = Invoice.objects.filter(status='PAID').annotate(date=TruncDate('paid_date')).values('date').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-date')
    return render(request, 'customers/daily_sales_report.html', {
        'sales': sales,
    })

@user_passes_test(lambda u: u.is_staff)
def monthly_sales_report(request):
    sales = Invoice.objects.filter(status='PAID').annotate(month=TruncMonth('paid_date')).values('month').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-month')
    return render(request, 'customers/monthly_sales_report.html', {
        'sales': sales,
    })

def hotspot_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        try:
            subscription = Subscription.objects.get(username=username, is_active=True)
            if subscription.password == password:  # In production, use proper password hashing
                messages.success(request, 'Hotspot login successful.')
                return redirect('customer_dashboard')
            else:
                messages.error(request, 'Invalid username or password.')
        except Subscription.DoesNotExist:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'customers/hotspot_login.html')