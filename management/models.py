from django.db import models
from django.contrib.auth.models import User

class Property(models.Model):
    """The 'Plot' or 'Apartment' name (e.g., Sunrise Apartments)."""
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    landlord = models.ForeignKey(User, on_delete=models.CASCADE, related_name="managed_properties", null=True)
    
    # --- GLOBAL UTILITY RATES ---
    water_rate_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=150.00)

    class Meta:
        verbose_name_plural = "Properties"

    def __str__(self):
        return self.name

class Unit(models.Model):
    """The specific house/room within a property."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="units")
    house_number = models.CharField(max_length=50)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_occupied = models.BooleanField(default=False)

    # --- UTILITY TOGGLES & READINGS ---
    has_water = models.BooleanField(default=True)
    # The reading at the START of the billing cycle
    previous_water_reading = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    # The reading at the END of the billing cycle (Updated by landlord via dashboard)
    last_water_reading = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    has_garbage = models.BooleanField(default=True)
    garbage_fee = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    
    has_service_charge = models.BooleanField(default=False)
    service_charge_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.property.name} - {self.house_number}"

class Tenant(models.Model):
    """The person currently occupying a unit (e.g., Jeff Jamlick)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tenant_profile', null=True, blank=True)
    name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=15)
    unit = models.OneToOneField(Unit, on_delete=models.SET_NULL, null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return self.name

class Payment(models.Model):
    """Logs for Transactions and Invoices."""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('FAILED', 'Failed'),
    ]

    TYPE_CHOICES = [
        ('MPESA', 'M-Pesa Payment'),
        ('CHARGE', 'Monthly Rent Charge'),
        ('MANUAL', 'Manual Adjustment'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='MPESA')
    
    # Stores the breakdown (e.g., Rent: 10k, Water: 500, Garbage: 500)
    note = models.TextField(null=True, blank=True)
    
    # Tracking IDs from Safaricom (Only for MPESA types)
    checkout_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    mpesa_receipt = models.CharField(max_length=20, unique=True, null=True, blank=True)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tenant.name} - {self.amount} ({self.transaction_type})"

class MaintenanceRequest(models.Model):
    """Issues reported by tenants (e.g., Leaking Tap)."""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="maintenance_requests")
    title = models.CharField(max_length=200)
    description = models.TextField()
    is_emergency = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    date_reported = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tenant.unit.house_number} - {self.title} ({self.status})"