from django.urls import path
from . import views

app_name = 'health_forms_services'

urlpatterns = [
    path('', views.health_forms_list, name='forms_list'),
    path('new/', views.manual_entry, name='manual_entry'),
    path('<int:pk>/', views.form_detail, name='form_detail'),
    path('<int:pk>/edit/', views.edit_form, name='edit_form'),
    path('<int:pk>/review/', views.review_form, name='review_form'),
    path('<int:pk>/delete/', views.delete_form, name='delete_form'),
    path('<int:pk>/export/', views.export_form_json, name='export_form'),
]
