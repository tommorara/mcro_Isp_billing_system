"""
URL configuration for universal_billing project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include
from django.contrib import admin  # Use default admin
from django.conf import settings
from django.conf.urls.static import static
from customers.views import hotspot_plans_api, hotspot_pay_api, daily_sales_report, monthly_sales_report

urlpatterns = [
    path('admin/', admin.site.urls),  # Use default admin site
    path('customer/', include('customers.urls')),
    path('payments/', include('payments.urls')),
    path('api/hotspot/plans/', hotspot_plans_api, name='hotspot_plans_api'),
    path('api/hotspot/pay/', hotspot_pay_api, name='hotspot_pay_api'),
    path('admin/daily-sales-report/', daily_sales_report, name='daily_sales_report'),
    path('admin/monthly-sales-report/', monthly_sales_report, name='monthly_sales_report'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)