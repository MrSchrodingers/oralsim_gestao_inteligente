from django.contrib import admin
from django.urls import include, path
from django_prometheus import exports

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/',     include('plugins.django_interface.urls')),
    path('metrics/', exports.ExportToDjangoView, name='metrics'),
]
