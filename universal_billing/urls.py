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
#from django.contrib import admin
#from django.urls import path

#urlpatterns = [
#    path('admin/', admin.site.urls),
#]

from django.urls import path, include
from django.http import HttpResponse
from rest_framework.routers import DefaultRouter
from companies.views import CompanyViewSet
from django.views.generic import TemplateView

router = DefaultRouter()
router.register(r'companies', CompanyViewSet, basename='company')

def tenant_view(request):
    tenant = request.tenant
    if tenant:
        return HttpResponse(f"Welcome to {tenant.name} (Schema: {tenant.schema_name})")
    return HttpResponse("Public Schema")

urlpatterns = [
    path('', tenant_view, name='tenant_home'),
    path('api/', include(router.urls)),
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
]
