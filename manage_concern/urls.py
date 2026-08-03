from django.urls import path

from . import views

app_name = 'manage_concern'

urlpatterns = [
    path('', views.concern_list, name='concern_list'),
    path('new/', views.concern_create, name='concern_create'),
    path('<int:pk>/', views.concern_detail, name='concern_detail'),
    path('<int:pk>/edit/', views.concern_edit, name='concern_edit'),
    path('<int:pk>/delete/', views.concern_delete, name='concern_delete'),
    path('api/search-users/', views.search_users, name='search_users'),
    path('api/user/<int:user_id>/prefill/', views.user_prefill, name='user_prefill'),
]
