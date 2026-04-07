from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'tenants', views.TenantViewSet)
router.register(r'payments', views.PaymentViewSet)

urlpatterns = [
    # Router URLs for the API (ViewSets)
    path('', include(router.urls)),

    # Function-based API for M-Pesa
    path('initiate-payment/', views.initiate_mpesa_payment, name='initiate-payment'),
    path('mpesa-callback/', views.mpesa_callback, name='mpesa-callback'),

    # HTML Dashboard Views
    path('dashboard/', views.tenant_dashboard, name='tenant-dashboard'),
    path('dashboard/<int:tenant_id>/', views.tenant_dashboard, name='tenant-dashboard-detail'),
    path('landlord/', views.landlord_dashboard, name='landlord-dashboard'),

    # NEW: AJAX path for updating utility readings
    path('update-water-reading/', views.update_water_reading, name='update-water-reading'),

    # NEW: PDF Receipt Download Path
    path('download-receipt/<int:payment_id>/', views.download_receipt, name='download_receipt'),
]