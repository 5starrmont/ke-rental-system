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

    # HTML Dashboard View
    path('dashboard/<int:tenant_id>/', views.tenant_dashboard, name='tenant-dashboard'),

    path('landlord/', views.landlord_dashboard, name='landlord-dashboard'),

    path('dashboard/', views.tenant_dashboard, name='tenant-dashboard'),
]