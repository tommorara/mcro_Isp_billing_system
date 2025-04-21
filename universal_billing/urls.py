from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from customers.api import CustomerViewSet, PackageViewSet, SubscriptionViewSet, VoucherViewSet
from customers import views

router = DefaultRouter()
router.register(r'customers', CustomerViewSet)
router.register(r'packages', PackageViewSet)
router.register(r'subscriptions', SubscriptionViewSet)
router.register(r'vouchers', VoucherViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/hotspot/plans/', views.hotspot_plans_api, name='hotspot_plans_api'),
    path('api/hotspot/pay/', views.hotspot_pay_api, name='hotspot_pay_api'),
    path('customer/login/', views.customer_login, name='customer_login'),
    path('customer/logout/', views.customer_logout, name='customer_logout'),
    path('customer/dashboard/', views.customer_dashboard, name='customer_dashboard'),
    path('customer/profile/', views.customer_profile, name='customer_profile'),
    path('customer/packages/', views.customer_packages, name='customer_packages'),
    path('customer/purchase/<int:package_id>/', views.customer_purchase, name='customer_purchase'),
    path('customer/plans/', views.customer_plans, name='customer_plans'),
    path('customer/invoices/', views.customer_invoices, name='customer_invoices'),
    path('customer/tickets/', views.customer_tickets, name='customer_tickets'),
    path('customer/tickets/<int:ticket_id>/', views.customer_ticket_detail, name='customer_ticket_detail'),
    path('customer/renew/<int:subscription_id>/', views.customer_renew, name='customer_renew'),
    path('customer/recharge/<int:subscription_id>/', views.recharge_subscription, name='recharge_subscription'),
    path('customer/redeem-voucher/', views.redeem_voucher, name='redeem_voucher'),
    path('customer/select-payment/<int:invoice_id>/', views.select_payment_method, name='select_payment_method'),
    path('reports/daily-sales/', views.daily_sales_report, name='daily_sales_report'),
    path('reports/monthly-sales/', views.monthly_sales_report, name='monthly_sales_report'),
    path('hotspot/login/', views.hotspot_login, name='hotspot_login'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)