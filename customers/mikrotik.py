# customers/mikrotik.py
from librouteros import connect
from customers.models import Customer

def sync_usage():
    api = connect(username='admin', password='pass', host='mikrotik_ip')
    for user in api.cmd('/ip/hotspot/user/print'):
        customer = Customer.objects.filter(email=user['email']).first()
        if customer:
            customer.data_usage = user.get('bytes-out', 0) / 1024 / 1024  # MB
            customer.save()