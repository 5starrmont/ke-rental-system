from django.core.management.base import BaseCommand
from management.models import Tenant, Payment
from management.utils import send_invoice_notification
from django.utils import timezone
from decimal import Decimal

class Command(BaseCommand):
    help = 'Generates consolidated rent & utility charges for all active tenants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset all tenant balances to 0 before generating new invoices',
        )

    def handle(self, *args, **options):
        # 1. Optional Reset
        if options['reset']:
            self.stdout.write(self.style.WARNING("Resetting all tenant balances to KES 0.00..."))
            Tenant.objects.all().update(balance=Decimal('0.00'))
            Payment.objects.filter(transaction_type='CHARGE').delete()

        # 2. Get active tenants
        tenants = Tenant.objects.exclude(unit__isnull=True)
        count = 0
        month_name = timezone.now().strftime("%B %Y")
        
        for tenant in tenants:
            unit = tenant.unit
            prop = unit.property
            
            # --- START BILL CALCULATION ---
            # Initial total is the base rent
            total_bill = unit.monthly_rent
            breakdown_parts = [f"Rent: {unit.monthly_rent}"]

            # Add Garbage Fee if toggled
            if unit.has_garbage:
                total_bill += unit.garbage_fee
                breakdown_parts.append(f"Garbage: {unit.garbage_fee}")

            # Add Service Charge if toggled
            if unit.has_service_charge:
                total_bill += unit.service_charge_fee
                breakdown_parts.append(f"Service: {unit.service_charge_fee}")

            # Add Water (Reading * Rate)
            if unit.has_water and unit.last_water_reading > 0:
                water_cost = (unit.last_water_reading * prop.water_rate_per_unit).quantize(Decimal('0.01'))
                total_bill += water_cost
                breakdown_parts.append(f"Water: {water_cost}")

            # Round the final total bill to 2 decimal places
            total_bill = total_bill.quantize(Decimal('0.01'))

            # Create a string for the 'note' field in the database
            full_breakdown = ", ".join(breakdown_parts)
            
            if total_bill <= 0:
                continue

            # 3. Save the Charge Record
            Payment.objects.create(
                tenant=tenant,
                amount=total_bill,
                transaction_type='CHARGE',
                status='PAID',
                note=full_breakdown  # Saving the breakdown here
            )

            # 4. Update the Tenant Balance
            tenant.balance += total_bill
            tenant.save()

            # 5. Notify via your existing utils.py function
            send_invoice_notification(tenant, total_bill, month_name)

            self.stdout.write(
                self.style.SUCCESS(f'Invoiced {tenant.name}: KES {total_bill} ({full_breakdown})')
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully processed {count} consolidated invoices.'))