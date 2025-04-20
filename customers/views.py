from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from datetime import timedelta
from .models import Customer, Package, Subscription, Invoice, SupportMessage, Voucher, Compensation
from payments.models import Payment
from payments.mpesa import initiate_stk_push
from functools import wraps
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import serializers
import json
import logging
import routeros_api
import MySQLdb
import subprocess

logger = logging.getLogger(__name__)

class PackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Package
        fields = ['id', 'name', 'download_bandwidth', 'upload_bandwidth', 'price', 'duration_minutes', 'duration_hours', 'duration_days']

@api_view(['GET'])
def hotspot_plans_api(request):
    packages = Package.objects.filter(connection_type='HOTSPOT')
    serializer = PackageSerializer(packages, many=True)
    return Response(serializer.data)

def connect_to_router(router):
    """Utility to connect to MikroTik router via API or VPN."""
    if router.connection_type == 'API':
        return routeros_api.RouterOsApiPool(
            router.ip_address, username=router.username,
            password=router.password, port=router.api_port
        ).get_api()
    elif router.connection_type == 'VPN':
        # Start VPN (example for OpenVPN)
        try:
            with open(f'vpn_creds/{router.id}.txt', 'w') as f:
                f.write(f"{router.vpn_username}\n{router.vpn_password}")
            subprocess.run([
                'openvpn', '--config', f'vpn_configs/{router.id}.ovpn',
                '--auth-user-pass', f'vpn_creds/{router.id}.txt',
                '--daemon'
            ], check=True)
            logger.info(f"Started VPN for router {router.name}")
            return routeros_api.RouterOsApiPool(
                router.ip_address, username=router.username,
                password=router.password, port=router.api_port
            ).get_api()
        except Exception as e:
            logger.error(f"VPN connection failed for {router.name}: {e}")
            raise
    elif router.connection_type == 'RADIUS':
        return None  # RADIUS handled by MikroTik
    raise ValueError(f"Unsupported connection type: {router.connection_type}")

@api_view(['GET', 'POST'])
def hotspot_pay_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            package_id = data.get('package_id')
            phone = data.get('phone')
            voucher_code = data.get('voucher_code')  # Optional voucher
            
            if not package_id or not phone:
                return Response({'error': 'Package ID and phone number are required'}, status=400)
            
            package = get_object_or_404(Package, id=package_id, connection_type='HOTSPOT')
            customer, created = Customer.objects.get_or_create(
                email=f"hotspot_{phone}@example.com".lower(),
                defaults={
                    'company': package.location.company,
                    'name': f"Hotspot User {phone}",
                    'phone': phone,
                    'password': make_password('hotspot123')
                }
            )
            
            if voucher_code:
                try:
                    voucher = Voucher.objects.get(code__iexact=voucher_code, is_active=True, redeemed_at__isnull=True)
                    if voucher.package != package:
                        return Response({'error': 'Voucher not valid for this package'}, status=400)
                    # Redeem voucher
                    duration = (
                        timedelta(minutes=package.duration_minutes or 0) +
                        timedelta(hours=package.duration_hours or 0) +
                        timedelta(days=package.duration_days or 0)
                    )
                    username = voucher.code if package.location.company.hotspot_login_method == 'VOUCHER' else f"hotspot_{phone}_{timezone.now().strftime('%Y%m%d%H%M%S')}"
                    subscription = Subscription.objects.create(
                        customer=customer,
                        package=package,
                        connection_type='HOTSPOT',
                        username=username,
                        password='hotspot123',
                        start_date=timezone.now(),
                        end_date=timezone.now() + duration,
                        router=package.router,
                        is_active=True
                    )
                    voucher.redeemed_at = timezone.now()
                    voucher.is_active = False
                    voucher.save()
                    
                    # Sync to MikroTik or RADIUS
                    router = package.router
                    if router.connection_type in ['API', 'VPN']:
                        try:
                            api = connect_to_router(router)
                            api.get_resource('/ip/hotspot/user').add(
                                name=username, password='hotspot123', profile=package.name,
                                limit_uptime=f"{package.duration_days or 0}d"
                            )
                        except Exception as e:
                            logger.error(f"Failed to sync {username} to MikroTik: {e}")
                    elif router.connection_type == 'RADIUS':
                        try:
                            db = MySQLdb.connect(
                                host=router.radius_server, user='radius_user',
                                passwd='radius_pass', db='radius'
                            )
                            cursor = db.cursor()
                            cursor.execute(
                                "INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                (username, 'Cleartext-Password', ':=', 'hotspot123')
                            )
                            db.commit()
                            db.close()
                        except Exception as e:
                            logger.error(f"Failed to sync {username} to RADIUS: {e}")
                    
                    return Response({
                        'status': 'success',
                        'username': subscription.username,
                        'password': subscription.password,
                        'login_method': package.location.company.hotspot_login_method
                    })
                except Voucher.DoesNotExist:
                    return Response({'error': 'Invalid or already used voucher'}, status=400)
            
            # M-Pesa payment flow
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
                transaction_id=f"HOTSPOT-{invoice.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                payment_method='MPESA',
                status='PENDING'
            )
            
            response = initiate_stk_push(phone, package.price, invoice.id, customer.id)
            if response.get('ResponseCode') == '0':
                payment.transaction_id = response.get('CheckoutRequestID')
                payment.save()
                return Response({
                    'status': 'pending',
                    'transaction_id': payment.transaction_id,
                    'message': 'Please complete the M-Pesa STK Push'
                })
            else:
                payment.status = 'FAILED'
                invoice.status = 'FAILED'
                payment.save()
                invoice.save()
                return Response({'error': 'Failed to initiate payment'}, status=400)
        
        except Exception as e:
            logger.error(f"Hotspot payment error: {e}")
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
                    # Create subscription after payment
                    package = payment.invoice.customer.subscription_set.last().package
                    duration = (
                        timedelta(minutes=package.duration_minutes or 0) +
                        timedelta(hours=package.duration_hours or 0) +
                        timedelta(days=package.duration_days or 0)
                    )
                    username = f"hotspot_{payment.customer.phone}_{timezone.now().strftime('%Y%m%d%H%M%S')}"
                    subscription = Subscription.objects.create(
                        customer=payment.customer,
                        package=package,
                        connection_type='HOTSPOT',
                        username=username,
                        password='hotspot123',
                        start_date=timezone.now(),
                        end_date=timezone.now() + duration,
                        router=package.router,
                        is_active=True
                    )
                    payment.invoice.subscription = subscription
                    payment.invoice.save()
                    
                    # Sync to MikroTik or RADIUS
                    router = package.router
                    if router.connection_type in ['API', 'VPN']:
                        try:
                            api = connect_to_router(router)
                            api.get_resource('/ip/hotspot/user').add(
                                name=username, password='hotspot123', profile=package.name,
                                limit_uptime=f"{package.duration_days or 0}d"
                            )
                        except Exception as e:
                            logger.error(f"Failed to sync {username} to MikroTik: {e}")
                    elif router.connection_type == 'RADIUS':
                        try:
                            db = MySQLdb.connect(
                                host=router.radius_server, user='radius_user',
                                passwd='radius_pass', db='radius'
                            )
                            cursor = db.cursor()
                            cursor.execute(
                                "INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                                (username, 'Cleartext-Password', ':=', 'hotspot123')
                            )
                            db.commit()
                            db.close()
                        except Exception as e:
                            logger.error(f"Failed to sync {username} to RADIUS: {e}")
                
                return Response({
                    'status': 'success',
                    'username': subscription.username,
                    'password': subscription.password,
                    'login_method': subscription.package.location.company.hotspot_login_method
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
        email = request.POST.get('email', '').strip().lower()  # Normalize to lowercase
        password = request.POST.get('password', '')
        try:
            customer = Customer.objects.get(email=email)
            if check_password(password, customer.password):
                request.session['customer_id'] = customer.id
                logger.info(f"Customer {email} logged in successfully")
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
    request.session.flush()
    messages.success(request, 'Logged out successfully.')
    return redirect('customer_login')

@customer_required
def customer_dashboard(request):
    customer = Customer.objects.get(id=request.session['customer_id'])
    subscriptions = Subscription.objects.filter(customer=customer)
    invoices = Invoice.objects.filter(customer=customer)
    notifications = SupportMessage.objects.filter(customer=customer, is_admin_reply=True, is_read=False)
    return render(request, 'customers/dashboard.html', {
        'customer': customer,
        'subscriptions': subscriptions,
        'invoices': invoices,
        'notifications': notifications,
    })

@customer_required
def customer_profile(request):
    customer = Customer.objects.get(id=request.session['customer_id'])
    compensations = Compensation.objects.filter(customer=customer)
    if request.method == 'POST':
        customer.name = request.POST.get('name')
        customer.email = request.POST.get('email', '').lower()
        customer.phone = request.POST.get('phone')
        customer.address = request.POST.get('address')
        password = request.POST.get('password')
        if password:
            customer.password = make_password(password)
        customer.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('customer_profile')
    return render(request, 'customers/profile.html', {
        'customer': customer,
        'compensations': compensations,
    })

@customer_required
def customer_packages(request):
    connection_type = request.GET.get('connection_type')
    router_id = request.GET.get('router_id')
    location_id = request.GET.get('location_id')
    packages = Package.objects.all()
    if connection_type:
        packages = packages.filter(connection_type=connection_type)
    if router_id:
        packages = packages.filter(router_id=router_id)
    if location_id:
        packages = packages.filter(location_id=location_id)
    return render(request, 'customers/packages.html', {'packages': packages})

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
def customer_notifications(request):
    customer = Customer.objects.get(id=request.session['customer_id'])
    notifications = SupportMessage.objects.filter(customer=customer, is_admin_reply=True).order_by('-created_at')
    if request.method == 'POST':
        notification_id = request.POST.get('notification_id')
        notification = get_object_or_404(SupportMessage, id=notification_id, customer=customer)
        notification.is_read = True
        notification.save()
        messages.success(request, 'Notification marked as read.')
        return redirect('customer_notifications')
    return render(request, 'customers/notifications.html', {
        'notifications': notifications,
        'customer': customer,
    })

@customer_required
def customer_support(request):
    customer = Customer.objects.get(id=request.session['customer_id'])
    if request.method == 'POST':
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        SupportMessage.objects.create(
            customer=customer,
            subject=subject,
            message=message,
            is_admin_reply=False
        )
        messages.success(request, 'Support message sent successfully.')
        return redirect('customer_support')
    messages_list = SupportMessage.objects.filter(customer=customer).order_by('-created_at')
    return render(request, 'customers/support.html', {
        'messages': messages_list,
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
        return redirect('select_payment_method', invoice_id=invoice.id)
    packages = Package.objects.filter(connection_type=subscription.connection_type, router=subscription.router)
    return render(request, 'customers/renew.html', {
        'subscription': subscription,
        'packages': packages,
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
        return redirect('select_payment_method', invoice_id=invoice.id)
    packages = Package.objects.filter(connection_type=subscription.connection_type, router=subscription.router)
    return render(request, 'customers/recharge.html', {
        'subscription': subscription,
        'packages': packages,
    })

def redeem_voucher(request):
    if request.method == 'POST':
        code = request.POST.get('code')
        phone = request.POST.get('phone')
        try:
            voucher = Voucher.objects.get(code__iexact=code, is_active=True, redeemed_at__isnull=True)
            package = voucher.package
            customer, created = Customer.objects.get_or_create(
                email=f"hotspot_{phone}@example.com".lower(),
                defaults={
                    'company': package.location.company,
                    'name': f"Hotspot User {phone}",
                    'phone': phone,
                    'password': make_password('hotspot123')
                }
            )
            duration = (
                timedelta(minutes=package.duration_minutes or 0) +
                timedelta(hours=package.duration_hours or 0) +
                timedelta(days=package.duration_days or 0)
            )
            username = voucher.code if package.location.company.hotspot_login_method == 'VOUCHER' else f"hotspot_{phone}_{timezone.now().strftime('%Y%m%d%H%M%S')}"
            subscription = Subscription.objects.create(
                customer=customer,
                package=package,
                connection_type='HOTSPOT',
                username=username,
                password='hotspot123',
                start_date=timezone.now(),
                end_date=timezone.now() + duration,
                router=package.router,
                is_active=True
            )
            voucher.redeemed_at = timezone.now()
            voucher.is_active = False
            voucher.save()
            
            # Sync to MikroTik or RADIUS
            router = package.router
            if router.connection_type in ['API', 'VPN']:
                try:
                    api = connect_to_router(router)
                    api.get_resource('/ip/hotspot/user').add(
                        name=username, password='hotspot123', profile=package.name,
                        limit_uptime=f"{package.duration_days or 0}d"
                    )
                except Exception as e:
                    logger.error(f"Failed to sync {username} to MikroTik: {e}")
            elif router.connection_type == 'RADIUS':
                try:
                    db = MySQLdb.connect(
                        host=router.radius_server, user='radius_user',
                        passwd='radius_pass', db='radius'
                    )
                    cursor = db.cursor()
                    cursor.execute(
                        "INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                        (username, 'Cleartext-Password', ':=', 'hotspot123')
                    )
                    db.commit()
                    db.close()
                except Exception as e:
                    logger.error(f"Failed to sync {username} to RADIUS: {e}")
            
            messages.success(request, f'Voucher redeemed! Username: {subscription.username}, Password: {subscription.password}')
            return redirect('redeem_voucher')
        except Voucher.DoesNotExist:
            messages.error(request, 'Invalid or already used voucher.')
    return render(request, 'customers/redeem_voucher.html')

def hotspot_login(request):
    # Deprecated: Hotspot logic moved to hotspot_login.html and hotspot.js
    return redirect('customer_login')