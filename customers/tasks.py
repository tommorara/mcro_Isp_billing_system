from celery import shared_task
from django.utils import timezone
from .models import Subscription, Package, Router, AuditLog, Voucher
import MySQLdb
import routeros_api
import logging
from datetime import timedelta
from django.conf import settings
from twilio.rest import Client

logger = logging.getLogger(__name__)

@shared_task
def sync_subscriptions_to_routers():
    for sub in Subscription.objects.filter(is_active=True):
        if not sub.router:
            logger.warning(f"No router assigned for subscription {sub.id}")
            continue
        try:
            api = routeros_api.RouterOsApiPool(
                sub.router.ip_address,
                username=sub.router.username,
                password=sub.router.password,
                port=8728,
                use_ssl=False,
                plaintext_login=True
            ).get_api()
            
            if sub.connection_type == 'HOTSPOT':
                api.get_resource('/ip/hotspot/user').call('remove', {'numbers': sub.username})
                api.get_resource('/ip/hotspot/user').call('add', {
                    'name': sub.username,
                    'password': sub.password,
                    'profile': sub.package.name.lower(),
                    'limit-bytes-in': int(sub.package.download_bandwidth * 1024 * 1024 * 1000),
                    'limit-bytes-out': int(sub.package.upload_bandwidth * 1024 * 1024 * 1000),
                    'shared-users': str(sub.package.shared_users),
                    'disabled': 'no'
                })
            elif sub.connection_type == 'PPPOE':
                api.get_resource('/ppp/secret').call('remove', {'numbers': sub.username})
                api.get_resource('/queue/simple').call('remove', {'name': f"q_{sub.username}"})
                api.get_resource('/ppp/secret').call('add', {
                    'name': sub.username,
                    'password': sub.password,
                    'service': 'pppoe',
                    'disabled': 'no'
                })
                api.get_resource('/queue/simple').call('add', {
                    'name': f"q_{sub.username}",
                    'target': sub.username,
                    'max-limit': f"{int(sub.package.upload_bandwidth * 1000000)}/{int(sub.package.download_bandwidth * 1000000)}"
                })
            elif sub.connection_type.startswith('VPN'):
                api.get_resource('/ppp/secret').call('remove', {'numbers': sub.username})
                api.get_resource('/ppp/secret').call('add', {
                    'name': sub.username,
                    'password': sub.password,
                    'service': sub.connection_type.lower().replace('vpn_', ''),
                    'remote-address': sub.static_ip or '',
                    'disabled': 'no'
                })
                if sub.package.upload_bandwidth and sub.package.download_bandwidth:
                    api.get_resource('/queue/simple').call('add', {
                        'name': f"q_{sub.username}",
                        'target': sub.username,
                        'max-limit': f"{int(sub.package.upload_bandwidth * 1000000)}/{int(sub.package.download_bandwidth * 1000000)}"
                    })
            
            AuditLog.objects.create(
                action='sync_to_router',
                model='Subscription',
                object_id=str(sub.id),
                user=None
            )
            logger.info(f"Synced subscription {sub.id} to router {sub.router.name}")
        except Exception as e:
            logger.error(f"Error syncing subscription {sub.id} to router {sub.router.name}: {e}")
            AuditLog.objects.create(
                action='sync_to_router_failed',
                model='Subscription',
                object_id=str(sub.id),
                user=None
            )

@shared_task
def sync_subscriptions_to_radius():
    try:
        db = MySQLdb.connect(
            host="localhost",
            user="radius_user",
            passwd="radius_pass",
            db="radius"
        )
        cursor = db.cursor()
        cursor.execute("TRUNCATE TABLE radcheck")
        cursor.execute("TRUNCATE TABLE radgroupcheck")
        cursor.execute("TRUNCATE TABLE radusergroup")
        
        for sub in Subscription.objects.filter(is_active=True):
            cursor.execute(
                "INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                (sub.username, 'Cleartext-Password', ':=', sub.password)
            )
            groupname = f"{sub.package.name}_{sub.connection_type}"
            cursor.execute(
                "INSERT INTO radgroupcheck (groupname, attribute, op, value) VALUES (%s, %s, %s, %s)",
                (groupname, 'Auth-Type', ':=', 'Accept')
            )
            if sub.connection_type == 'HOTSPOT':
                cursor.execute(
                    "INSERT INTO radgroupcheck (groupname, attribute, op, value) VALUES (%s, %s, %s, %s)",
                    (groupname, 'Simultaneous-Use', ':=', str(sub.package.shared_users))
                )
            cursor.execute(
                "INSERT INTO radusergroup (username, groupname, priority) VALUES (%s, %s, %s)",
                (sub.username, groupname, 1)
            )
        
        db.commit()
        db.close()
        AuditLog.objects.create(
            action='sync_to_radius',
            model='Subscription',
            object_id='all',
            user=None
        )
        logger.info("Synced subscriptions to FreeRADIUS")
    except Exception as e:
        logger.error(f"Error syncing subscriptions to FreeRADIUS: {e}")
        AuditLog.objects.create(
            action='sync_to_radius_failed',
            model='Subscription',
            object_id='all',
            user=None
        )

@shared_task
def disable_expired_subscriptions():
    try:
        expired = Subscription.objects.filter(end_date__lt=timezone.now(), is_active=True)
        for sub in expired:
            sub.is_active = False
            sub.save()
            if sub.router:
                try:
                    api = routeros_api.RouterOsApiPool(
                        sub.router.ip_address,
                        username=sub.router.username,
                        password=sub.router.password,
                        port=8728,
                        use_ssl=False,
                        plaintext_login=True
                    ).get_api()
                    if sub.connection_type == 'HOTSPOT':
                        api.get_resource('/ip/hotspot/user').call('set', {
                            'numbers': sub.username,
                            'disabled': 'yes'
                        })
                    elif sub.connection_type in ['PPPOE'] or sub.connection_type.startswith('VPN'):
                        api.get_resource('/ppp/secret').call('set', {
                            'numbers': sub.username,
                            'disabled': 'yes'
                        })
                        api.get_resource('/queue/simple').call('remove', {'name': f"q_{sub.username}"})
                    AuditLog.objects.create(
                        action='disable_subscription',
                        model='Subscription',
                        object_id=str(sub.id),
                        user=None
                    )
                    logger.info(f"Disabled subscription {sub.id}")
                except Exception as e:
                    logger.error(f"Error disabling subscription {sub.id} on router: {e}")
        sync_subscriptions_to_radius.delay()
    except Exception as e:
        logger.error(f"Error disabling subscriptions: {e}")
        AuditLog.objects.create(
            action='disable_subscriptions_failed',
            model='Subscription',
            object_id='all',
            user=None
        )

@shared_task
def update_subscription_from_compensation(compensation_id):
    from .models import Compensation
    try:
        comp = Compensation.objects.get(id=compensation_id)
        if comp.subscription and comp.subscription.is_active:
            duration = timedelta(hours=comp.extra_hours or 0) + timedelta(days=comp.extra_days or 0)
            comp.subscription.end_date += duration
            comp.subscription.save()
            AuditLog.objects.create(
                action='apply_compensation',
                model='Subscription',
                object_id=str(comp.subscription.id),
                user=None
            )
            logger.info(f"Applied compensation {comp.id} to subscription {comp.subscription.id}")
            sync_subscriptions_to_routers.delay()
            sync_subscriptions_to_radius.delay()
    except Exception as e:
        logger.error(f"Error applying compensation {compensation_id}: {e}")
        AuditLog.objects.create(
            action='apply_compensation_failed',
            model='Compensation',
            object_id=str(compensation_id),
            user=None
        )

@shared_task
def send_voucher_sms(voucher_id):
    try:
        voucher = Voucher.objects.get(id=voucher_id)
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=f"Your ISP One Hotspot voucher: {voucher.code} for {voucher.package.name}. Redeem at https://yourdomain.com/customer/redeem_voucher/",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=voucher.package.location.company.phone or '+254123456789'
        )
        logger.info(f"Sent SMS for voucher {voucher.code}: {message.sid}")
        AuditLog.objects.create(
            action='send_voucher_sms',
            model='Voucher',
            object_id=str(voucher.id),
            user=None
        )
    except Exception as e:
        logger.error(f"Error sending SMS for voucher {voucher_id}: {e}")
        AuditLog.objects.create(
            action='send_voucher_sms_failed',
            model='Voucher',
            object_id=str(voucher_id),
            user=None
        )