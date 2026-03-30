from rest_framework import serializers
from .models import Tenant, Payment, Property, Unit

class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = '__all__'

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        # We removed mpesa_code, so we use the new fields instead
        fields = [
            'id', 'tenant', 'amount', 'status', 
            'checkout_id', 'mpesa_receipt', 
            'date_created', 'date_updated'
        ]