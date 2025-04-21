from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from datetime import timedelta
from .models import Customer, Package, Subscription, Voucher
from .serializers import CustomerSerializer, PackageSerializer, SubscriptionSerializer, VoucherSerializer
from .utils import send_sms
import logging

logger = logging.getLogger(__name__)

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    @action(detail=False, methods=['post'])
    def create_customer(self, request):
        try:
            data = request.data
            company_id = data.get('company_id')
            name = data.get('name')
            email = data.get('email')
            phone = data.get('phone')
            address = data.get('address', '')
            password = data.get('password', 'user123')

            if not all([company_id, name, email, phone]):
                return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

            customer, created = Customer.objects.get_or_create(
                email=email.lower(),
                defaults={
                    'company_id': company_id,
                    'name': name,
                    'phone': phone,
                    'address': address,
                    'password': make_password(password)
                }
            )
            if created:
                send_sms(phone, f"Welcome to {customer.company.name}! Your account has been created.")
                logger.info(f"Created customer {email}")
                return Response({'status': 'success', 'customer_id': customer.id}, status=status.HTTP_201_CREATED)
            else:
                return Response({'status': 'exists', 'customer_id': customer.id}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Failed to create customer: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PackageViewSet(viewsets.ModelViewSet):
    queryset = Package.objects.all()
    serializer_class = PackageSerializer

    @action(detail=False, methods=['get'])
    def by_connection_type(self, request):
        connection_type = request.query_params.get('connection_type')
        if connection_type:
            packages = Package.objects.filter(connection_type=connection_type)
        else:
            packages = Package.objects.all()
        serializer = PackageSerializer(packages, many=True)
        return Response(serializer.data)

class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer

    @action(detail=False, methods=['post'])
    def create_subscription(self, request):
        try:
            data = request.data
            customer_id = data.get('customer_id')
            package_id = data.get('package_id')
            username = data.get('username')
            password = data.get('password', 'user123')

            if not all([customer_id, package_id, username]):
                return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

            customer = Customer.objects.get(id=customer_id)
            package = Package.objects.get(id=package_id)
            duration = (
                timedelta(minutes=package.duration_minutes or 0) +
                timedelta(hours=package.duration_hours or 0) +
                timedelta(days=package.duration_days or 0)
            )
            subscription = Subscription.objects.create(
                customer=customer,
                package=package,
                connection_type=package.connection_type,
                username=username,
                password=password,
                start_date=timezone.now(),
                end_date=timezone.now() + duration,
                router=package.router,
                is_active=True
            )
            send_sms(customer.phone, f"Subscription created: {package.name}. Username: {username}")
            logger.info(f"Created subscription for {username}")
            return Response({'status': 'success', 'subscription_id': subscription.id}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Failed to create subscription: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VoucherViewSet(viewsets.ModelViewSet):
    queryset = Voucher.objects.all()
    serializer_class = VoucherSerializer

    @action(detail=False, methods=['post'])
    def redeem(self, request):
        try:
            data = request.data
            code = data.get('code')
            customer_id = data.get('customer_id')

            if not all([code, customer_id]):
                return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

            customer = Customer.objects.get(id=customer_id)
            voucher = Voucher.objects.get(code__iexact=code, is_active=True, redeemed_at__isnull=True)
            package = voucher.package
            duration = (
                timedelta(minutes=package.duration_minutes or 0) +
                timedelta(hours=package.duration_hours or 0) +
                timedelta(days=package.duration_days or 0)
            )
            username = voucher.code if package.connection_type == 'HOTSPOT' and package.company.hotspot_login_method == 'VOUCHER' else f"{package.connection_type.lower()}_{customer.phone}_{timezone.now().strftime('%Y%m%d%H%M%S')}"
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

            send_sms(customer.phone, f"Voucher redeemed! Username: {subscription.username}, Password: {subscription.password}")
            logger.info(f"Redeemed voucher {code} for customer {customer.email}")
            return Response({
                'status': 'success',
                'subscription_id': subscription.id,
                'username': subscription.username,
                'password': subscription.password
            }, status=status.HTTP_200_OK)
        except Voucher.DoesNotExist:
            return Response({'error': 'Invalid or already used voucher'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Failed to redeem voucher: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)