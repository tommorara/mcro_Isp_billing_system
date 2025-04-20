import requests
import base64
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
import logging
from .models import Payment
from customers.models import Subscription, Invoice

logger = logging.getLogger(__name__)

def get_mpesa_token():
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET
    api_url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    auth = base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()
    headers = {'Authorization': f'Basic {auth}'}
    response = requests.get(api_url, headers=headers)
    return response.json()['access_token']

def initiate_stk_push(phone, amount, invoice_id, customer_id):
    token = get_mpesa_token()
    api_url = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password = base64.b64encode(f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}".encode()).decode()
    data = {
        'BusinessShortCode': settings.MPESA_SHORTCODE,
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': 'CustomerPayBillOnline',
        'Amount': str(amount),
        'PartyA': phone,
        'PartyB': settings.MPESA_SHORTCODE,
        'PhoneNumber': phone,
        'CallBackURL': settings.MPESA_CALLBACK_URL,
        'AccountReference': f"Inv-{invoice_id}",
        'TransactionDesc': f"Payment for invoice {invoice_id}"
    }
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    response = requests.post(api_url, json=data, headers=headers)
    logger.info(f"STK Push response: {response.json()}")
    return response.json()

def mpesa_callback(request):
    if request.method == 'POST':
        data = request.POST
        logger.info(f"M-Pesa callback: {data}")
        result_code = data.get('ResultCode')
        checkout_request_id = data.get('CheckoutRequestID')
        try:
            payment = Payment.objects.get(transaction_id=checkout_request_id)
            if result_code == '0':
                payment.status = 'SUCCESS'
                payment.invoice.status = 'PAID'
                subscription = payment.invoice.subscription
                package = subscription.package
                subscription.start_date = timezone.now()
                subscription.end_date = timezone.now() + timedelta(days=package.duration_days)
                subscription.is_active = True
                subscription.save()
                payment.invoice.save()
                payment.save()
                logger.info(f"Payment {checkout_request_id} successful")
            else:
                payment.status = 'FAILED'
                payment.invoice.status = 'FAILED'
                payment.invoice.save()
                payment.save()
                logger.warning(f"Payment {checkout_request_id} failed")
            return JsonResponse({'status': 'ok'})
        except Payment.DoesNotExist:
            logger.error(f"Payment {checkout_request_id} not found")
            return JsonResponse({'status': 'error'}, status=400)
    return JsonResponse({'status': 'error'}, status=400)