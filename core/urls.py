from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),          # Fixed: added 's' to urls
    path('api/', include('management.urls')), 
    path('', include('management.urls')),     
]