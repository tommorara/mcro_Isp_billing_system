from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from datetime import timedelta
from functools import wraps
import logging
from .models import Customer, Package, Subscription, Invoice, SupportMessage
from payments.views import initiate_stk_push
from payments.models import Payment

logger = logging.getLogger(__name__)

def customer_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('customer_id'):
            return redirect('customer_login')
        return view_func(request, *args, **kwargs)
    return wrapper

def customer_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        logger.info(f"Login attempt for {email}")
        try:
            customer = Customer.objects.get(email=email)
            if check_password(password, customer.password):
                request.session['customer_id'] = customer.id
                logger.info(f"Login successful for {email}")
                return redirect('customer_dashboard')
            else:
                logger.warning(f"Invalid password for {email}")
                messages.error(request, 'Invalid email or password.')
        except Customer.DoesNotExist:
            logger.warning(f"Customer not found: {email}")
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
    notifications = SupportMessage.objects.filter(customer=customer, is_read=False)
    current_packages = subscriptions.values_list('package__id', flat=True)
    recommendations = Package.objects.exclude(id__in=current_packages).order_by('-speed')[:3]
    return render(request, 'customers/dashboard.html', {
        'customer': customer,
        'subscriptions': subscriptions,
        'notifications': notifications,
        'recommendations': recommendations,
    })

@customer_required
def customer_packages(request):
    connection_type = request.GET.get('connection_type', 'HOTSPOT')
    packages = Package.objects.filter(connection_type=connection_type)
    return render(request, 'customers/packages.html', {
        'packages': packages,
        'connection_type': connection_type,
    })

@customer_required
def customer_plans(request):
    customer = Customer.objects.get(id=request.session['customer_id'])
    subscriptions = Subscription.objects.filter(customer=customer)
    return render(request, 'customers/plans.html', {
        'customer': customer,
        'subscriptions': subscriptions,
    })

@customer_required
def customer_invoices(request):
    customer = Customer.objects.get(id=request.session['customer_id'])
    invoices = Invoice.objects.filter(customer=customer)
    return render(request, 'customers/invoices.html', {
        'invoices': invoices,
        'customer': customer,
    })

@customer_required
def customer_notifications(request):
    customer = Customer.objects.get(id=request.session['customer_id'])
    notifications = SupportMessage.objects.filter(customer=customer)
    if request.method == 'POST':
        notification_id = request.POST.get('notification_id')
        notification = get_object_or_404(SupportMessage, id=notification_id, customer=customer)
        notification.is_read = True
        notification.save()
        messages.success(request, 'Notification marked as read.')
        return redirect('customer_notifications')
    return render(request, 'customers/notifications.html', {
        'customer': customer,
        'notifications': notifications,
    })

@customer_required
def customer_profile(request):
    customer = Customer.objects.get(id=request.session['customer_id'])
    if request.method == 'POST':
        customer.name = request.POST.get('name')
        customer.email = request.POST.get('email')
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
        payment = Payment.objects.create(
            customer=customer,
            invoice=invoice,
            amount=package.price,
            transaction_id=f"INV-{invoice.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            payment_method='MPESA'
        )
        response = initiate_stk_push(customer.phone, package.price, invoice.id, customer.id)
        if response.get('ResponseCode') == '0':
            payment.transaction_id = response.get('CheckoutRequestID')
            payment.save()
            messages.success(request, 'Payment initiated. Please complete the STK Push.')
            return redirect('customer_dashboard')
        else:
            payment.status = 'FAILED'
            invoice.status = 'FAILED'
            payment.save()
            invoice.save()
            messages.error(request, 'Failed to initiate payment.')
    packages = Package.objects.filter(connection_type=subscription.connection_type)
    return render(request, 'customers/renew.html', {
        'subscription': subscription,
        'packages': packages,
    })