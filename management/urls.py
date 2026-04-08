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
    
    # Professional Landlord Portal Routes (Dedicated Pages)
    path('landlord/', views.landlord_dashboard, name='landlord-dashboard'),
    path('landlord/tenants/', views.tenants_list, name='tenants-list'),
    path('landlord/settings/', views.property_settings, name='property-settings'),

    # Caretaker Portal Routes
    path('caretaker/', views.caretaker_dashboard, name='caretaker-dashboard'),
    path('update-maintenance-status/', views.update_maintenance_status, name='update-maintenance-status'),

    # Web-based Itemized Invoice View
    path('invoice/<int:payment_id>/', views.view_invoice, name='view-invoice'),

    # AJAX Action Paths
    path('update-water-reading/', views.update_water_reading, name='update-water-reading'),
    path('report-maintenance/', views.report_maintenance, name='report-maintenance'),
    path('generate-invoices/', views.generate_monthly_invoices, name='generate-invoices'),
    path('update-unit-settings/', views.update_unit_settings, name='update-unit-settings'),

    # PDF Receipt/Invoice Download Path
    path('download-receipt/<int:payment_id>/', views.download_receipt, name='download_receipt'),
]