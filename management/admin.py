from django.contrib import admin
from .models import Property, Unit, Tenant, Payment

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('name', 'location')

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('house_number', 'property', 'monthly_rent', 'is_occupied')
    list_filter = ('property', 'is_occupied')

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'unit', 'balance')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    # Updated to match your new model fields
    list_display = ('tenant', 'amount', 'status', 'mpesa_receipt', 'date_created')
    list_filter = ('status', 'date_created')
    readonly_fields = ('date_created', 'date_updated', 'checkout_id')