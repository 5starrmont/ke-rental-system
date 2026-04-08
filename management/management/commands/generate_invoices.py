from django.core.management.base import BaseCommand
from management.models import Tenant, Payment, Property
from management.utils import send_invoice_notification
from django.utils import timezone
from decimal import Decimal

class Command(BaseCommand):
    help = 'Generates consolidated rent & utility charges for all active tenants using Global Settings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset all tenant balances to 0 before generating new invoices',
        )

    def handle(self, *args, **options):
        # 1. Fetch Global Property Settings
        prop_settings = Property.objects.first()
        if not prop_settings:
            self.stdout.write(self.style.ERROR("CRITICAL: No Property settings found. Please configure settings in the dashboard first."))
            return

        # 2. Optional Reset
        if options['reset']:
            self.stdout.write(self.style.WARNING("Resetting all tenant balances to KES 0.00..."))
            Tenant.objects.all().update(balance=Decimal('0.00'))
            # Note: Deleting charges is fine for a 'hard reset' during development
            Payment.objects.filter(transaction_type='CHARGE').delete()

        # 3. Get active tenants
        tenants = Tenant.objects.exclude(unit__isnull=True)
        count = 0
        month_name = timezone.now().strftime("%B %Y")
        
        for tenant in tenants:
            unit = tenant.unit
            
            # --- START BILL CALCULATION ---
            # Initial total is the base rent
            total_bill = unit.monthly_rent
            breakdown_parts = [f"Rent: {unit.monthly_rent}"]

            # Add Garbage Fee: Check Global Toggle AND Unit Toggle
            if prop_settings.garbage_billing_enabled and unit.has_garbage:
                # Pull the current rate from Global Settings
                g_fee = prop_settings.garbage_fee_default
                total_bill += g_fee
                breakdown_parts.append(f"Garbage: {g_fee}")

            # Add Service Charge if toggled on the Unit
            if unit.has_service_charge:
                total_bill += unit.service_charge_fee
                breakdown_parts.append(f"Service: {unit.service_charge_fee}")

            # Add Water: Check Global Toggle AND Unit Toggle
            if prop_settings.water_billing_enabled and unit.has_water:
                # Consumption = New - Prev
                consumed = unit.last_water_reading - unit.previous_water_reading
                if consumed < 0:
                    consumed = 0
                
                # Use Global Water Rate
                w_rate = prop_settings.water_rate_per_unit
                water_cost = (Decimal(consumed) * w_rate).quantize(Decimal('0.01'))
                total_bill += water_cost
                breakdown_parts.append(f"Water ({consumed} units): {water_cost}")
                
                # Important: Shift readings after successful calculation
                unit.previous_water_reading = unit.last_water_reading
                unit.save()

            # Round the final total bill to 2 decimal places
            total_bill = total_bill.quantize(Decimal('0.01'))

            # Create a string for the 'note' field in the database
            full_breakdown = ", ".join(breakdown_parts)
            
            if total_bill <= 0:
                continue

            # 4. Save the Charge Record
            Payment.objects.create(
                tenant=tenant,
                amount=total_bill,
                transaction_type='CHARGE',
                status='PAID',
                note=full_breakdown
            )

            # 5. Update the Tenant Balance
            tenant.balance += total_bill
            tenant.save()

            # 6. Notify via your existing utils.py function
            send_invoice_notification(tenant, total_bill, month_name)

            self.stdout.write(
                self.style.SUCCESS(f'Invoiced {tenant.name}: KES {total_bill} ({full_breakdown})')
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully processed {count} consolidated invoices.'))