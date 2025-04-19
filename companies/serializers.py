from rest_framework import serializers
from companies.models import Company

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'email', 'created_at', 'schema_name']