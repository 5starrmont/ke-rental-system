from django.core.management.base import BaseCommand
from management.models import Tenant

class Command(BaseCommand):
    help = 'Adds monthly rent to all active tenant balances'

    def handle(self, *args, **kwargs):
        tenants = Tenant.objects.exclude(unit__isnull=True)
        count = 0
        
        for tenant in tenants:
            rent_amount = tenant.unit.monthly_rent
            tenant.balance += rent_amount
            tenant.save()
            self.stdout.write(
                self.style.SUCCESS(f'Invoiced {tenant.name}: Added KES {rent_amount}')
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully generated {count} invoices.'))