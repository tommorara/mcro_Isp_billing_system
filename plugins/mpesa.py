from plugins.base import PaymentPlugin
from payments.mpesa import initiate_stk_push  # Your existing M-Pesa logic

class MpesaPlugin(PaymentPlugin):
    def initiate_payment(self, amount, phone, invoice_id, customer_id):
        return initiate_stk_push(phone, amount, invoice_id, customer_id)

    def check_payment_status(self, transaction_id):
        # Implement status check if available in your M-Pesa integration
        return {'status': 'PENDING'}  # Placeholder