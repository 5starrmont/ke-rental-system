from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django_daraja.mpesa.core import MpesaClient

from .models import Tenant, Payment
from .serializers import TenantSerializer, PaymentSerializer

class TenantViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows tenants to be viewed.
    """
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer

class PaymentViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows payments to be viewed or created.
    """
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

@api_view(['POST'])
def initiate_mpesa_payment(request):
    """
    Triggers STK Push and creates a PENDING payment record with the CheckoutRequestID.
    """
    tenant_id = request.data.get('tenant_id')
    amount = request.data.get('amount')

    try:
        tenant = Tenant.objects.get(id=tenant_id)
        callback_url = 'https://oversevere-micki-excursionary.ngrok-free.dev/api/mpesa-callback/'
        
        cl = MpesaClient()
        account_reference = f'House-{tenant.unit.house_number}'
        transaction_desc = f'Rent for {tenant.name}'
        
        # 1. Trigger the STK Push
        response = cl.stk_push(tenant.phone_number, int(amount), account_reference, transaction_desc, callback_url)
        
        # 2. Extract the CheckoutRequestID from the response
        res_data = response.json()
        checkout_id = res_data.get('CheckoutRequestID')

        # 3. Create a record in our DB so we can track it later
        Payment.objects.create(
            tenant=tenant,
            amount=amount,
            checkout_id=checkout_id,
            status='PENDING'
        )
        
        return JsonResponse({
            'status': 'Success',
            'message': 'STK Push sent. Record created as PENDING.',
            'checkout_id': checkout_id
        })

    except Tenant.DoesNotExist:
        return JsonResponse({'status': 'Error', 'message': 'Tenant not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'Error', 'message': str(e)}, status=500)

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def mpesa_callback(request):
    """
    Safaricom hits this endpoint. Updates status and subtracts from Tenant balance.
    """
    data = request.data
    stk_callback = data.get('Body', {}).get('stkCallback', {})
    result_code = stk_callback.get('ResultCode')
    checkout_id = stk_callback.get('CheckoutRequestID')
    
    print(f"----------- CALLBACK RECEIVED FOR ID: {checkout_id} -----------")
    
    try:
        # Find the specific payment we started earlier
        payment = Payment.objects.get(checkout_id=checkout_id)
        
        # Prevent double-processing if Safaricom sends the same callback twice
        if payment.status != 'PAID' and result_code == 0:
            # Success Path
            items = stk_callback.get('CallbackMetadata', {}).get('Item', [])
            metadata = {item['Name']: item.get('Value') for item in items}
            
            # 1. Update Payment record
            payment.status = 'PAID'
            payment.mpesa_receipt = metadata.get('MpesaReceiptNumber')
            payment.save()
            
            # 2. Update Tenant Balance
            tenant = payment.tenant
            tenant.balance -= payment.amount
            tenant.save()
            
            print(f"✅ SUCCESS: Payment {payment.id} PAID. Tenant {tenant.name} balance is now {tenant.balance}.")
            
        elif result_code != 0:
            # Failure Path
            desc = stk_callback.get('ResultDesc')
            payment.status = 'FAILED'
            payment.save()
            print(f"❌ FAILED: Code {result_code} - {desc}")
            
    except Payment.DoesNotExist:
        print(f"⚠️ WARNING: Received callback for {checkout_id} but no record exists in our DB.")
    
    print("----------------------------------------------------------------")
    
    return Response({"ResultCode": 0, "ResultDesc": "Accepted"})