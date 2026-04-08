import africastalking
import time
import decimal
from datetime import timedelta
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.conf import settings 

from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from django_daraja.mpesa.core import MpesaClient

from .models import Tenant, Payment, Unit, Property, MaintenanceRequest
from .serializers import TenantSerializer, PaymentSerializer
from .utils import generate_receipt_pdf  # Import our updated PDF utility

# --- Helper Logic for User Roles ---

def is_caretaker(user):
    """Checks if a user belongs to the 'Caretakers' group or is staff."""
    return user.groups.filter(name='Caretakers').exists() or user.is_staff

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
        # Keeping your exact callback URL
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

# --- Landlord Portal (Dedicated Pages) ---

@login_required
def landlord_dashboard(request):
    """Global financial overview for the property manager."""
    if not request.user.is_staff:
        return HttpResponse("Unauthorized", status=403)

    # Calculate Totals based on transaction types
    total_billed = Payment.objects.filter(transaction_type='CHARGE').aggregate(Sum('amount'))['amount__sum'] or 0
    total_collected = Payment.objects.filter(transaction_type='MPESA', status='PAID').aggregate(Sum('amount'))['amount__sum'] or 0
    total_outstanding = Tenant.objects.aggregate(Sum('balance'))['balance__sum'] or 0
    
    recent_payments = Payment.objects.all().order_by('-date_created')[:10]
    
    return render(request, 'management/landlord.html', {
        'total_billed': total_billed,
        'total_collected': total_collected,
        'total_outstanding': total_outstanding,
        'recent_payments': recent_payments,
    })

@login_required
def tenants_list(request):
    """Dedicated management page for Units and Tenants."""
    if not request.user.is_staff:
        return HttpResponse("Unauthorized", status=403)
        
    search_query = request.GET.get('search', '')
    tenants = Tenant.objects.all()
    if search_query:
        tenants = tenants.filter(name__icontains=search_query)

    return render(request, 'management/tenants.html', {
        'tenants': tenants,
        'search_query': search_query
    })

@login_required
def property_settings(request):
    """Dedicated page for Global Property configuration."""
    if not request.user.is_staff:
        return HttpResponse("Unauthorized", status=403)
    
    property_obj = Property.objects.first()
    
    if request.method == 'POST':
        # Update Identity
        property_obj.name = request.POST.get('name')
        property_obj.location = request.POST.get('location')
        
        # Update Rates
        property_obj.water_rate_per_unit = request.POST.get('water_rate')
        property_obj.garbage_fee_default = request.POST.get('garbage_fee')
        
        # Update Toggles (Checkboxes only appear in POST if they are checked)
        property_obj.water_billing_enabled = 'water_enabled' in request.POST
        property_obj.garbage_billing_enabled = 'garbage_enabled' in request.POST
        
        property_obj.save()
        return render(request, 'management/settings.html', {'property': property_obj, 'success': True})

    return render(request, 'management/settings.html', {'property': property_obj})

# --- Caretaker Portal ---

@login_required
def caretaker_dashboard(request):
    """
    Portal restricted to users in the 'Caretakers' group or Staff.
    """
    if not is_caretaker(request.user):
        return HttpResponse("Unauthorized: This portal is for Caretakers only.", status=403)

    units = Unit.objects.filter(is_occupied=True).order_by('house_number')
    pending_maintenance = MaintenanceRequest.objects.exclude(status='RESOLVED').order_by('-is_emergency', '-date_reported')

    return render(request, 'management/caretaker.html', {
        'units': units,
        'maintenance': pending_maintenance
    })

@login_required
@api_view(['POST'])
def update_maintenance_status(request):
    """AJAX view to update request status (e.g., Pending -> In Progress)."""
    request_id = request.data.get('request_id')
    new_status = request.data.get('status')
    
    try:
        maintenance = MaintenanceRequest.objects.get(id=request_id)
        maintenance.status = new_status
        maintenance.save()
        return JsonResponse({'status': 'success'})
    except MaintenanceRequest.DoesNotExist:
        return JsonResponse({'status': 'error'}, status=404)

# --- Dashboard Views ---

@login_required
def tenant_dashboard(request, tenant_id=None):
    """
    Shows the dashboard. 
    Redirects caretakers to their specific portal if no tenant_id is provided.
    """
    # Auto-redirect Caretaker users to their field dashboard
    if is_caretaker(request.user) and not tenant_id:
        return redirect('caretaker-dashboard')

    try:
        is_landlord_view = False
        if tenant_id:
            # Viewing a specific tenant (Admin/Landlord mode)
            tenant = get_object_or_404(Tenant, id=tenant_id)
            is_landlord_view = True
        else:
            # Viewing own profile (Tenant mode)
            tenant = request.user.tenant_profile
            
        payments = tenant.payments.all().order_by('-date_created')
        maintenance_requests = tenant.maintenance_requests.all().order_by('-date_reported')

        return render(request, 'management/dashboard.html', {
            'tenant': tenant,
            'payments': payments,
            'maintenance_requests': maintenance_requests,
            'is_landlord_view': is_landlord_view
        })
    except (AttributeError, Tenant.DoesNotExist):
        return render(request, 'management/dashboard.html', {
            'error': "No tenant profile found or linked to this account."
        })

# --- AJAX Action Views ---

@login_required
@api_view(['POST'])
def update_water_reading(request):
    """Updates the water units consumed for a specific unit via AJAX."""
    unit_id = request.data.get('unit_id')
    reading = request.data.get('reading')

    try:
        unit = Unit.objects.get(id=unit_id)
        unit.last_water_reading = reading
        unit.save()
        return JsonResponse({'status': 'success', 'message': f'Units updated for {unit.house_number}'})
    except Unit.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Unit not found'}, status=404)

@login_required
@api_view(['POST'])
def report_maintenance(request):
    """Allows a tenant to submit a maintenance request via AJAX."""
    try:
        tenant = request.user.tenant_profile
        title = request.data.get('title')
        description = request.data.get('description')
        is_emergency = request.data.get('is_emergency', False)

        if not title or not description:
            return JsonResponse({'status': 'error', 'message': 'Title and Description are required.'}, status=400)

        MaintenanceRequest.objects.create(
            tenant=tenant,
            title=title,
            description=description,
            is_emergency=is_emergency
        )
        return JsonResponse({'status': 'success', 'message': 'Request submitted successfully!'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@api_view(['POST'])
def update_unit_settings(request):
    """Updates utility toggles and fixed fees for a unit via AJAX."""
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    unit_id = request.data.get('unit_id')
    try:
        unit = Unit.objects.get(id=unit_id)
        
        # Update toggles
        unit.has_water = request.data.get('has_water', unit.has_water)
        unit.has_garbage = request.data.get('has_garbage', unit.has_garbage)
        unit.has_service_charge = request.data.get('has_service_charge', unit.has_service_charge)
        
        # Update fees
        unit.monthly_rent = request.data.get('monthly_rent', unit.monthly_rent)
        unit.garbage_fee = request.data.get('garbage_fee', unit.garbage_fee)
        unit.service_charge_fee = request.data.get('service_charge_fee', unit.service_charge_fee)
        
        unit.save()
        return JsonResponse({'status': 'success', 'message': f'Settings updated for {unit.house_number}'})
    except Unit.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Unit not found'}, status=404)

@login_required
@api_view(['POST'])
def generate_monthly_invoices(request):
    """Loop through all tenants and generate charges based on Global Property Settings."""
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    # 1. Fetch Global Property Settings
    prop = Property.objects.first()
    if not prop:
        return JsonResponse({'status': 'error', 'message': 'No Property settings found.'}, status=404)

    tenants = Tenant.objects.filter(unit__is_occupied=True)
    count = 0

    for tenant in tenants:
        unit = tenant.unit
        total_amount = unit.monthly_rent
        breakdown = [f"Rent: {unit.monthly_rent}"]

        # 2. Global Garbage Logic (Pulling from Property Settings)
        if prop.garbage_billing_enabled and unit.has_garbage:
            total_amount += prop.garbage_fee_default
            breakdown.append(f"Garbage: {prop.garbage_fee_default}")

        # 3. Add Service Charge if toggled on the Unit
        if unit.has_service_charge:
            total_amount += unit.service_charge_fee
            breakdown.append(f"Service: {unit.service_charge_fee}")

        # 4. Global Water Logic (New - Previous * Global Rate)
        if prop.water_billing_enabled and unit.has_water:
            consumed = unit.last_water_reading - unit.previous_water_reading
            if consumed < 0:
                consumed = 0
            
            water_total = decimal.Decimal(consumed) * prop.water_rate_per_unit
            total_amount += water_total
            breakdown.append(f"Water ({consumed} units): {water_total}")
            
            # Shift readings for next cycle
            unit.previous_water_reading = unit.last_water_reading
            unit.save()

        # 5. Create the Charge record
        Payment.objects.create(
            tenant=tenant,
            amount=total_amount,
            transaction_type='CHARGE',
            status='PAID',
            note=", ".join(breakdown)
        )

        # 6. Update Tenant Balance
        tenant.balance += total_amount
        tenant.save()
        count += 1

    return JsonResponse({'status': 'success', 'message': f'Invoices generated for {count} tenants.'})

# --- Web & PDF Invoice/Receipt Views ---

@login_required
def view_invoice(request, payment_id):
    """Renders a web-based itemized view of an invoice."""
    payment = get_object_or_404(Payment, id=payment_id)
    
    if not request.user.is_staff and payment.tenant.user != request.user:
        return HttpResponse("Unauthorized", status=403)
    
    start_date = payment.date_created - timedelta(days=30)
    end_date = payment.date_created

    breakdown = []
    if payment.note:
        items = payment.note.split(', ')
        for item in items:
            if ':' in item:
                parts = item.split(': ')
                breakdown.append({'desc': parts[0], 'amt': parts[1]})
    
    return render(request, 'management/invoice_detail.html', {
        'payment': payment,
        'breakdown': breakdown,
        'property': payment.tenant.unit.property,
        'start_date': start_date,
        'end_date': end_date
    })

@login_required
def download_receipt(request, payment_id):
    """Generates and returns a PDF receipt."""
    payment = get_object_or_404(Payment, id=payment_id)
    
    if not request.user.is_staff and payment.tenant.user != request.user:
         return HttpResponse("Unauthorized", status=403)
    
    pdf_content = generate_receipt_pdf(payment)
    response = HttpResponse(bytes(pdf_content), content_type='application/pdf')
    
    prefix = "Receipt" if payment.transaction_type == 'MPESA' else "Invoice"
    filename = f"{prefix}_{payment.mpesa_receipt or payment.id}.pdf"
    
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    
    return response