from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views # Add this import

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('management.urls')),
    path('', include('management.urls')),
    
    # Add this line for the custom login
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
]