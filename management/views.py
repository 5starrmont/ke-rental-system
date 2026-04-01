import africastalking
import time
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.conf import settings 

from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from django_daraja.mpesa.core import MpesaClient

from .models import Tenant, Payment
from .serializers import TenantSerializer, PaymentSerializer

# --- Helper Function for SMS ---

def send_payment_notification(tenant, amount):
    """Helper to send SMS via Africa's Talking with Retry Logic and Settings Init"""
    try:
        africastalking.initialize(settings.AT_USERNAME, settings.AT_API_KEY)
        sms = africastalking.SMS

        phone = tenant.phone_number
        if phone.startswith('0'):
            phone = f"+254{phone[1:]}"
        elif not phone.startswith('+'):
            phone = f"+{phone}"

        message = (
            f"Confirmed! Received KES {amount} for Unit {tenant.unit.house_number}. "
            f"Your new balance is KES {tenant.balance}. Thank you for using Ke-Rental."
        )
        
        for attempt in range(3):
            try:
                response = sms.send(message, [phone])
                print(f"--- SMS SENT SUCCESSFULLY (Attempt {attempt+1}): {response} ---")
                return 
            except Exception as e:
                print(f"--- SMS ATTEMPT {attempt+1} FAILED: {str(e)} ---")
                if attempt < 2:
                    time.sleep(1)
                else:
                    print("--- SMS GAVE UP AFTER 3 ATTEMPTS ---")
    except Exception as init_e:
        print(f"--- SMS INITIALIZATION FAILED: {str(init_e)} ---")

# --- API ViewSets ---

class TenantViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows tenants to be viewed."""
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer

class PaymentViewSet(viewsets.ModelViewSet):
    """API endpoint that allows payments to be viewed or created."""
    queryset = Payment.objects.all().order_by('-date_created')
    serializer_class = PaymentSerializer

# --- M-Pesa Integration Logic ---

@api_view(['POST'])
def initiate_mpesa_payment(request):
    """Triggers STK Push and prints the actual response for debugging."""
    tenant_id = request.data.get('tenant_id')
    amount = request.data.get('amount')

    try:
        tenant = Tenant.objects.get(id=tenant_id)
        callback_url = settings.MPESA_CONFIG.get('CALLBACK_URL', 'https://oversevere-micki-excursionary.ngrok-free.dev/api/mpesa-callback/')
        
        cl = MpesaClient()
        account_reference = f'House-{tenant.unit.house_number}'
        transaction_desc = f'Rent for {tenant.name}'
        
        response = cl.stk_push(tenant.phone_number, int(amount), account_reference, transaction_desc, callback_url)
        
        print(f"--- SAFARICOM RAW RESPONSE: {response.text} ---")
        
        res_data = response.json()
        checkout_id = res_data.get('CheckoutRequestID')

        if checkout_id:
            Payment.objects.create(
                tenant=tenant,
                amount=amount,
                checkout_id=checkout_id,
                transaction_type='MPESA',
                status='PENDING'
            )
            return JsonResponse({
                'status': 'Success',
                'message': 'STK Push sent.',
                'checkout_id': checkout_id
            })
        else:
            error_msg = res_data.get('errorMessage', 'Unknown Safaricom Error')
            print(f"--- SAFARICOM ERROR: {error_msg} ---")
            return JsonResponse({'status': 'Error', 'message': error_msg}, status=400)

    except Tenant.DoesNotExist:
        return JsonResponse({'status': 'Error', 'message': 'Tenant not found'}, status=404)
    except Exception as e:
        print(f"--- CODE EXCEPTION: {str(e)} ---")
        return JsonResponse({'status': 'Error', 'message': str(e)}, status=500)

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def mpesa_callback(request):
    """Safaricom callback. Updates status, reconciles balance, and sends SMS."""
    data = request.data
    stk_callback = data.get('Body', {}).get('stkCallback', {})
    result_code = stk_callback.get('ResultCode')
    checkout_id = stk_callback.get('CheckoutRequestID')
    
    print(f"----------- CALLBACK RECEIVED FOR ID: {checkout_id} -----------")
    
    try:
        payment = Payment.objects.get(checkout_id=checkout_id)
        
        if payment.status != 'PAID' and result_code == 0:
            items = stk_callback.get('CallbackMetadata', {}).get('Item', [])
            metadata = {item['Name']: item.get('Value') for item in items}
            
            payment.status = 'PAID'
            payment.mpesa_receipt = metadata.get('MpesaReceiptNumber')
            payment.save()
            
            tenant = payment.tenant
            tenant.balance -= payment.amount
            tenant.save()
            
            send_payment_notification(tenant, payment.amount)
            print(f"✅ SUCCESS: Payment PAID and SMS Notification triggered.")
            
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
    """Shows the dashboard ONLY for the logged-in tenant."""
    try:
        tenant = request.user.tenant_profile
        payments = tenant.payments.all().order_by('-date_created')
        return render(request, 'management/dashboard.html', {
            'tenant': tenant,
            'payments': payments
        })
    except (AttributeError, Tenant.DoesNotExist):
        return render(request, 'management/dashboard.html', {
            'error': "No tenant profile linked to this account."
        })

@login_required
def landlord_dashboard(request):
    """Global financial overview for the property manager."""
    search_query = request.GET.get('search', '')
    tenants = Tenant.objects.all()
    
    if search_query:
        tenants = tenants.filter(name__icontains=search_query)

    # Calculate Totals based on transaction types
    total_billed = Payment.objects.filter(transaction_type='CHARGE').aggregate(Sum('amount'))['amount__sum'] or 0
    total_collected = Payment.objects.filter(transaction_type='MPESA', status='PAID').aggregate(Sum('amount'))['amount__sum'] or 0
    total_outstanding = Tenant.objects.aggregate(Sum('balance'))['balance__sum'] or 0
    
    recent_payments = Payment.objects.all().order_by('-date_created')[:10]
    
    return render(request, 'management/landlord.html', {
        'total_billed': total_billed,
        'total_collected': total_collected,
        'total_outstanding': total_outstanding,
        'tenants': tenants,
        'recent_payments': recent_payments,
        'search_query': search_query
    })