from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TenantViewSet, 
    PaymentViewSet, 
    initiate_mpesa_payment, 
    mpesa_callback
)

router = DefaultRouter()
router.register(r'tenants', TenantViewSet)
router.register(r'payments', PaymentViewSet)

urlpatterns = [
    path('', include(router.urls)),
    
    # The endpoint to start the payment
    path('initiate-payment/', initiate_mpesa_payment, name='initiate-payment'),
    
    # The endpoint where Safaricom sends the receipt
    path('mpesa-callback/', mpesa_callback, name='mpesa-callback'),
]