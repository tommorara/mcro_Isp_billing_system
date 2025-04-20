from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Customer, Package, Subscription
from .serializers import CustomerSerializer, PackageSerializer, SubscriptionSerializer

class CustomerDetail(APIView):
    def get(self, request):
        customer = Customer.objects.get(id=request.session['customer_id'])
        serializer = CustomerSerializer(customer)
        return Response(serializer.data)

class PackageList(APIView):
    def get(self, request):
        connection_type = request.GET.get('connection_type')
        packages = Package.objects.all()
        if connection_type:
            packages = packages.filter(connection_type=connection_type)
        serializer = PackageSerializer(packages, many=True)
        return Response(serializer.data)

class SubscriptionList(APIView):
    def get(self, request):
        customer = Customer.objects.get(id=request.session['customer_id'])
        subscriptions = Subscription.objects.filter(customer=customer)
        serializer = SubscriptionSerializer(subscriptions, many=True)
        return Response(serializer.data)