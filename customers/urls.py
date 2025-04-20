from django.urls import path
from . import views
from .api import PackageList, CompanyDetail

urlpatterns = [
    path('login/', views.customer_login, name='customer_login'),
    path('logout/', views.customer_logout, name='customer_logout'),
    path('dashboard/', views.customer_dashboard, name='customer_dashboard'),
    path('profile/', views.customer_profile, name='customer_profile'),
    path('packages/', views.customer_packages, name='customer_packages'),
    path('plans/', views.customer_plans, name='customer_plans'),
    path('invoices/', views.customer_invoices, name='customer_invoices'),
    path('notifications/', views.customer_notifications, name='customer_notifications'),
    path('support/', views.customer_support, name='customer_support'),
    path('renew/<int:subscription_id>/', views.customer_renew, name='customer_renew'),
    path('recharge/<int:subscription_id>/', views.recharge_subscription, name='recharge_subscription'),
    path('redeem_voucher/', views.redeem_voucher, name='redeem_voucher'),
    path('hotspot/', views.hotspot_login, name='hotspot_login'),
    path('api/packages/', PackageList.as_view(), name='package_list'),
    path('api/company/', CompanyDetail.as_view(), name='company_detail'),
]