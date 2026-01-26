from django.urls import path
from . import views

app_name = 'health_tips'

urlpatterns = [
    path('', views.health_tips, name='health_tips_list'),
    path('upload-image/', views.upload_image, name='upload_image'),
    path('<int:tip_id>/', views.health_tip_detail, name='health_tip_detail'),
    path('create/', views.create_health_tip, name='create_health_tip'),
    path('<int:tip_id>/edit/', views.edit_health_tip, name='edit_health_tip'),
    path('<int:tip_id>/delete/', views.delete_health_tip, name='delete_health_tip'),
    path('<int:tip_id>/toggle-status/', views.toggle_health_tip_status, name='toggle_health_tip_status'),
]
