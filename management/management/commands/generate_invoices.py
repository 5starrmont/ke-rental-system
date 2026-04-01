from django.core.management.base import BaseCommand
from management.models import Tenant, Payment
from django.utils import timezone

class Command(BaseCommand):
    help = 'Adds monthly rent to all active tenant balances and creates a charge record'

    def handle(self, *args, **kwargs):
        # Only bill tenants who actually have a unit assigned
        tenants = Tenant.objects.exclude(unit__isnull=True)
        count = 0
        
        for tenant in tenants:
            rent_amount = tenant.unit.monthly_rent
            
            # 1. Update the Tenant's Balance
            tenant.balance += rent_amount
            tenant.save()

            # 2. Create an Invoice/Charge record in the Payment table
            Payment.objects.create(
                tenant=tenant,
                amount=rent_amount,
                transaction_type='CHARGE',
                status='PAID' # Charges are 'PAID' in the sense that the invoice is issued
            )

            self.stdout.write(
                self.style.SUCCESS(f'Invoiced {tenant.name}: Added KES {rent_amount}')
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully generated {count} invoices for {timezone.now().strftime("%B %Y")}.'))