from django.urls import path
from . import views, api

urlpatterns = [
    path('login/', views.customer_login, name='customer_login'),
    path('logout/', views.customer_logout, name='customer_logout'),
    path('dashboard/', views.customer_dashboard, name='customer_dashboard'),
    path('packages/', views.customer_packages, name='customer_packages'),
    path('plans/', views.customer_plans, name='customer_plans'),
    path('invoices/', views.customer_invoices, name='customer_invoices'),
    path('notifications/', views.customer_notifications, name='customer_notifications'),
    path('profile/', views.customer_profile, name='customer_profile'),
    path('renew/<int:subscription_id>/', views.customer_renew, name='customer_renew'),
    path('api/customer/', api.CustomerDetail.as_view(), name='api_customer'),
    path('api/packages/', api.PackageList.as_view(), name='api_packages'),
    path('api/subscriptions/', api.SubscriptionList.as_view(), name='api_subscriptions'),
]