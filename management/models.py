from django.db import models

class Property(models.Model):
    """The 'Plot' or 'Apartment' name (e.g., Sunrise Apartments)."""
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=200)

    class Meta:
        verbose_name_plural = "Properties"

    def __str__(self):
        return self.name

class Unit(models.Model):
    """The specific house/room within a property."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="units")
    house_number = models.CharField(max_length=50)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    is_occupied = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.property.name} - {self.house_number}"

class Tenant(models.Model):
    """The person currently occupying a unit."""
    name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=15)
    unit = models.OneToOneField(Unit, on_delete=models.SET_NULL, null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return self.name

class Payment(models.Model):
    """Logs for M-Pesa Transactions."""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('FAILED', 'Failed'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Tracking IDs from Safaricom
    checkout_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    mpesa_receipt = models.CharField(max_length=20, unique=True, null=True, blank=True)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tenant.name} - {self.amount} ({self.status})"