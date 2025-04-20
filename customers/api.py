from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Package
from companies.models import Company

class PackageList(APIView):
    def get(self, request):
        connection_type = request.query_params.get('connection_type')
        packages = Package.objects.all()
        if connection_type:
            packages = packages.filter(connection_type=connection_type)
        data = [{
            'id': pkg.id,
            'name': pkg.name,
            'connection_type': pkg.connection_type,
            'download_bandwidth': pkg.download_bandwidth,
            'upload_bandwidth': pkg.upload_bandwidth,
            'shared_users': pkg.shared_users,
            'price': str(pkg.price),
            'duration_minutes': pkg.duration_minutes,
            'duration_hours': pkg.duration_hours,
            'duration_days': pkg.duration_days,
        } for pkg in packages]
        return Response(data)

class CompanyDetail(APIView):
    def get(self, request):
        company = Company.objects.first()
        if not company:
            return Response({'hotspot_login_method': 'TRANSACTION'})
        return Response({'hotspot_login_method': company.hotspot_login_method})