from celery import shared_task
from django.utils import timezone
from .models import Subscription
from librouteros import connect
from django.db import connections
import logging

logger = logging.getLogger(__name__)

@shared_task
def disable_expired_subscriptions():
    subscriptions = Subscription.objects.filter(is_active=True, end_date__lte=timezone.now())
    for sub in subscriptions:
        sub.is_active = False
        sub.save()
        logger.info(f"Disabled subscription {sub.id} for {sub.customer.name}")

@shared_task
def sync_subscriptions_to_routers():
    subscriptions = Subscription.objects.filter(is_active=True)
    for sub in subscriptions:
        if not sub.router:
            logger.warning(f"No router assigned for subscription {sub.id}")
            continue
        try:
            api = connect(
                username=sub.router.username,
                password=sub.router.password,
                host=sub.router.ip_address
            )
            if sub.connection_type == 'HOTSPOT':
                api.cmd('/ip/hotspot/user/add', {
                    'name': sub.username,
                    'password': sub.password,
                    'profile': sub.package.name.lower(),
                    'disabled': 'no'
                })
            elif sub.connection_type == 'PPPOE':
                api.cmd('/ppp/secret/add', {
                    'name': sub.username,
                    'password': sub.password,
                    'service': 'pppoe',
                    'disabled': 'no'
                })
            elif sub.connection_type == 'STATIC':
                api.cmd('/ip/address/add', {
                    'address': f"{sub.static_ip}/32",
                    'interface': 'ether1',
                    'disabled': 'no'
                })
            elif sub.connection_type in ('VPN_PPT', 'VPN_L2TP', 'VPN_OVPN'):
                service = 'pptp' if sub.connection_type == 'VPN_PPT' else 'l2tp' if sub.connection_type == 'VPN_L2TP' else 'ovpn'
                api.cmd('/ppp/secret/add', {
                    'name': sub.username,
                    'password': sub.password,
                    'service': service,
                    'disabled': 'no'
                })
            logger.info(f"Synced {sub.username} to {sub.router.name}")
        except Exception as e:
            logger.error(f"Failed to sync {sub.username} to {sub.router.name}: {e}")

@shared_task
def sync_subscriptions_to_freeradius():
    subscriptions = Subscription.objects.filter(is_active=True, connection_type__in=['HOTSPOT', 'PPPOE'])
    with connections['radius'].cursor() as cursor:
        for sub in subscriptions:
            try:
                # Insert/Update radcheck (username, password)
                cursor.execute("""
                    INSERT INTO radcheck (username, attribute, op, value)
                    VALUES (%s, 'Cleartext-Password', ':=', %s)
                    ON DUPLICATE KEY UPDATE value=%s
                """, [sub.username, sub.password, sub.password])
                # Insert/Update radgroupcheck (group settings, e.g., package name)
                cursor.execute("""
                    INSERT INTO radgroupcheck (groupname, attribute, op, value)
                    VALUES (%s, 'Auth-Type', ':=', 'Accept')
                    ON DUPLICATE KEY UPDATE value='Accept'
                """, [sub.package.name.lower()])
                # Link user to group
                cursor.execute("""
                    INSERT INTO radusergroup (username, groupname, priority)
                    VALUES (%s, %s, 1)
                    ON DUPLICATE KEY UPDATE groupname=%s
                """, [sub.username, sub.package.name.lower(), sub.package.name.lower()])
                logger.info(f"Synced {sub.username} to FreeRADIUS")
            except Exception as e:
                logger.error(f"Failed to sync {sub.username} to FreeRADIUS: {e}")