from django.contrib import admin
from .models import Property, Unit, Tenant, Payment, MaintenanceRequest

@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    """Admin interface for managing tenant issues."""
    list_display = ('tenant', 'unit_number', 'title', 'is_emergency', 'status', 'date_reported')
    list_filter = ('status', 'is_emergency', 'date_reported')
    search_fields = ('title', 'tenant__name', 'tenant__unit__house_number')
    list_editable = ('status',)
    readonly_fields = ('date_reported', 'date_updated')

    def unit_number(self, obj):
        return obj.tenant.unit.house_number if obj.tenant.unit else "N/A"
    unit_number.short_description = 'Unit'

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
    list_display = ('tenant', 'amount', 'status', 'mpesa_receipt', 'date_created')
    list_filter = ('status', 'date_created')
    readonly_fields = ('date_created', 'date_updated', 'checkout_id')