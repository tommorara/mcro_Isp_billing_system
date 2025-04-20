import requests
import base64
import json
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

def get_access_token():
    try:
        consumer_key = settings.MPESA_CONSUMER_KEY
        consumer_secret = settings.MPESA_CONSUMER_SECRET
        api_url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
        headers = {
            'Authorization': 'Basic ' + base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()
        }
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        token = response.json().get('access_token')
        if not token:
            logger.error("Failed to obtain M-Pesa access token: No token in response")
            raise Exception("No access token received")
        logger.info("Successfully obtained M-Pesa access token")
        return token
    except Exception as e:
        logger.error(f"Error obtaining M-Pesa access token: {str(e)}")
        raise

def initiate_stk_push(phone_number, amount, invoice_id, customer_id):
    try:
        access_token = get_access_token()
        api_url = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
        headers = {'Authorization': f'Bearer {access_token}'}
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode(
            f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}".encode()
        ).decode()
        payload = {
            'BusinessShortCode': settings.MPESA_SHORTCODE,
            'Password': password,
            'Timestamp': timestamp,
            'TransactionType': 'CustomerPayBillOnline',
            'Amount': str(int(amount)),  # Ensure integer amount
            'PartyA': phone_number.replace('+', ''),
            'PartyB': settings.MPESA_SHORTCODE,
            'PhoneNumber': phone_number.replace('+', ''),
            'CallBackURL': settings.MPESA_CALLBACK_URL,
            'AccountReference': f'INV-{invoice_id}',
            'TransactionDesc': f'Payment for Invoice {invoice_id} (Customer {customer_id})'
        }
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        result = response.json()
        if result.get('ResponseCode') != '0':
            logger.error(f"STK Push failed: {result.get('ResponseDescription')}")
        else:
            logger.info(f"STK Push initiated for invoice {invoice_id}, CheckoutRequestID: {result.get('CheckoutRequestID')}")
        return result
    except Exception as e:
        logger.error(f"Error initiating STK Push for invoice {invoice_id}: {str(e)}")
        return {'ResponseCode': '1', 'ResponseDescription': str(e)}