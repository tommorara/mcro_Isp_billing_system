from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.core.files.storage import FileSystemStorage
from .models import Payment
from customers.models import Invoice, Subscription, Customer, Package, Voucher
from customers.tasks import sync_subscriptions_to_routers, sync_subscriptions_to_radius
from .mpesa import initiate_stk_push
import json
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

@csrf_exempt
def mpesa_callback(request):
    if request.method != 'POST':
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid request method'})

    try:
        data = json.loads(request.body)
        callback_data = data.get('Body', {}).get('stkCallback', {})
        result_code = callback_data.get('ResultCode')
        checkout_request_id = callback_data.get('CheckoutRequestID')
        
        if not checkout_request_id:
            logger.error("No CheckoutRequestID in callback")
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Missing CheckoutRequestID'})

        try:
            payment = Payment.objects.get(transaction_id=checkout_request_id)
            invoice = payment.invoice
            customer = payment.customer
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for CheckoutRequestID: {checkout_request_id}")
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Payment not found'})

        if result_code == 0:
            payment.status = 'SUCCESS'
            invoice.status = 'PAID'
            invoice.paid_date = timezone.now()
            
            if not invoice.subscription:
                package = Package.objects.filter(invoice__id=invoice.id).first() or Package.objects.filter(connection_type='HOTSPOT').first()
                if package:
                    duration = (
                        timedelta(minutes=package.duration_minutes or 0) +
                        timedelta(hours=package.duration_hours or 0) +
                        timedelta(days=package.duration_days or 0)
                    )
                    username = (
                        checkout_request_id if package.location.company.hotspot_login_method == 'TRANSACTION' else
                        f"hotspot_{customer.phone}_{timezone.now().strftime('%Y%m%d%H%M%S')}" if package.location.company.hotspot_login_method == 'PHONE' else
                        Voucher.objects.create(package=package).code
                    )
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
                    invoice.subscription = subscription
                    invoice.save()
                    sync_subscriptions_to_routers.delay()
                    sync_subscriptions_to_radius.delay()
                    logger.info(f"Hotspot subscription created for customer {customer.id}, username: {username}")
            
            payment.save()
            invoice.save()
            logger.info(f"Payment {checkout_request_id} successful for customer {customer.id}")
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})
        else:
            payment.status = 'FAILED'
            invoice.status = 'FAILED'
            payment.save()
            invoice.save()
            logger.warning(f"Payment {checkout_request_id} failed: {callback_data.get('ResultDesc')}")
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})
    
    except Exception as e:
        logger.error(f"Error processing M-Pesa callback: {str(e)}")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Server error'})

def select_payment_method(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id, customer__id=request.session.get('customer_id'))
    if invoice.status != 'PENDING':
        messages.error(request, 'This invoice is not pending payment.')
        return redirect('customer_invoices')

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        if payment_method == 'MPESA':
            payment = Payment.objects.create(
                customer=invoice.customer,
                invoice=invoice,
                amount=invoice.amount,
                transaction_id=f"MPESA-{invoice.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                payment_method='MPESA',
                status='PENDING'
            )
            response = initiate_stk_push(invoice.customer.phone, invoice.amount, invoice.id, invoice.customer.id)
            if response.get('ResponseCode') == '0':
                payment.transaction_id = response.get('CheckoutRequestID')
                payment.save()
                messages.success(request, 'Please complete the M-Pesa STK Push to proceed.')
            else:
                payment.status = 'FAILED'
                invoice.status = 'FAILED'
                payment.save()
                invoice.save()
                messages.error(request, 'Failed to initiate M-Pesa payment.')
            return redirect('customer_invoices')
        
        elif payment_method == 'BANK_TRANSFER':
            proof_file = request.FILES.get('proof_file')
            if not proof_file:
                messages.error(request, 'Please upload proof of payment.')
                return redirect('select_payment_method', invoice_id=invoice_id)
            
            payment = Payment.objects.create(
                customer=invoice.customer,
                invoice=invoice,
                amount=invoice.amount,
                transaction_id=f"BANK-{invoice.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                payment_method='BANK_TRANSFER',
                status='AWAITING_VERIFICATION',
                proof_file=proof_file
            )
            messages.success(request, 'Bank transfer proof uploaded. Awaiting admin verification.')
            return redirect('customer_invoices')
        
        elif payment_method == 'CASH':
            payment = Payment.objects.create(
                customer=invoice.customer,
                invoice=invoice,
                amount=invoice.amount,
                transaction_id=f"CASH-{invoice.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                payment_method='CASH',
                status='AWAITING_VERIFICATION'
            )
            messages.success(request, 'Cash payment recorded. Please visit our office to complete payment.')
            return redirect('customer_invoices')

    return render(request, 'payments/select_payment_method.html', {'invoice': invoice})