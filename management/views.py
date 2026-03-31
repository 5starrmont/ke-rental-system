from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.db.models import Sum
from django.contrib.auth.decorators import login_required

from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from django_daraja.mpesa.core import MpesaClient

from .models import Tenant, Payment
from .serializers import TenantSerializer, PaymentSerializer

# --- API ViewSets ---

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
    queryset = Payment.objects.all().order_by('-date_created')
    serializer_class = PaymentSerializer

# --- M-Pesa Integration Logic ---

@api_view(['POST'])
def initiate_mpesa_payment(request):
    """
    Triggers STK Push and creates a PENDING payment record.
    """
    tenant_id = request.data.get('tenant_id')
    amount = request.data.get('amount')

    try:
        tenant = Tenant.objects.get(id=tenant_id)
        # Ensure this URL matches your active ngrok tunnel
        callback_url = 'https://oversevere-micki-excursionary.ngrok-free.dev/api/mpesa-callback/'
        
        cl = MpesaClient()
        account_reference = f'House-{tenant.unit.house_number}'
        transaction_desc = f'Rent for {tenant.name}'
        
        # 1. Trigger STK Push
        response = cl.stk_push(tenant.phone_number, int(amount), account_reference, transaction_desc, callback_url)
        res_data = response.json()
        checkout_id = res_data.get('CheckoutRequestID')

        # 2. Create local record
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
    Safaricom callback. Updates status and reconciles tenant balance.
    """
    data = request.data
    stk_callback = data.get('Body', {}).get('stkCallback', {})
    result_code = stk_callback.get('ResultCode')
    checkout_id = stk_callback.get('CheckoutRequestID')
    
    print(f"----------- CALLBACK RECEIVED FOR ID: {checkout_id} -----------")
    
    try:
        payment = Payment.objects.get(checkout_id=checkout_id)
        
        if payment.status != 'PAID' and result_code == 0:
            # Success: Extract metadata
            items = stk_callback.get('CallbackMetadata', {}).get('Item', [])
            metadata = {item['Name']: item.get('Value') for item in items}
            
            # Update Payment
            payment.status = 'PAID'
            payment.mpesa_receipt = metadata.get('MpesaReceiptNumber')
            payment.save()
            
            # Reconcile Tenant Balance
            tenant = payment.tenant
            tenant.balance -= payment.amount
            tenant.save()
            
            print(f"✅ SUCCESS: Payment {payment.id} PAID. Tenant {tenant.name} balance updated.")
            
        elif result_code != 0:
            payment.status = 'FAILED'
            payment.save()
            print(f"❌ FAILED: Code {result_code} - {stk_callback.get('ResultDesc')}")
            
    except Payment.DoesNotExist:
        print(f"⚠️ WARNING: Callback for {checkout_id} received but no record found.")
    
    return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

# --- Dashboard Views ---

@login_required
def tenant_dashboard(request):
    """
    Shows the dashboard ONLY for the logged-in tenant.
    No tenant_id needed in the URL anymore.
    """
    try:
        # Link to the OneToOneField user profile
        tenant = request.user.tenant_profile
        payments = tenant.payments.all().order_by('-date_created')
        return render(request, 'management/dashboard.html', {
            'tenant': tenant,
            'payments': payments
        })
    except (AttributeError, Tenant.DoesNotExist):
        # Fallback if an admin logs in without a tenant profile
        return render(request, 'management/dashboard.html', {
            'error': "No tenant profile linked to this account."
        })

@login_required
def landlord_dashboard(request):
    """
    Global financial overview for the property manager.
    Only accessible by logged-in users (Staff/Admin).
    """
    search_query = request.GET.get('search', '')
    tenants = Tenant.objects.all()
    
    if search_query:
        tenants = tenants.filter(name__icontains=search_query)

    total_expected = Tenant.objects.aggregate(Sum('balance'))['balance__sum'] or 0
    total_collected = Payment.objects.filter(status='PAID').aggregate(Sum('amount'))['amount__sum'] or 0
    recent_payments = Payment.objects.all().order_by('-date_created')[:10]
    
    return render(request, 'management/landlord.html', {
        'total_expected': total_expected,
        'total_collected': total_collected,
        'tenants': tenants,
        'recent_payments': recent_payments,
        'search_query': search_query
    })