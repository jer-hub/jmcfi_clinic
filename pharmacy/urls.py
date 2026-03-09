from django.urls import path
from . import views

app_name = 'pharmacy'

urlpatterns = [
    # Dashboard
    path('', views.pharmacy_dashboard, name='dashboard'),

    # Medicines
    path('medicines/', views.medicine_list, name='medicine_list'),
    path('medicines/add/', views.medicine_create, name='medicine_create'),
    path('medicines/<int:medicine_id>/', views.medicine_detail, name='medicine_detail'),
    path('medicines/<int:medicine_id>/edit/', views.medicine_edit, name='medicine_edit'),

    # Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.category_create, name='category_create'),
    path('categories/<int:category_id>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:category_id>/delete/', views.category_delete, name='category_delete'),

    # Batches
    path('batches/', views.batch_list, name='batch_list'),
    path('batches/add/', views.batch_create, name='batch_create'),
    path('batches/<int:batch_id>/edit/', views.batch_edit, name='batch_edit'),

    # Suppliers
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/add/', views.supplier_create, name='supplier_create'),
    path('suppliers/<int:supplier_id>/edit/', views.supplier_edit, name='supplier_edit'),

    # Purchase Orders
    path('orders/', views.purchase_order_list, name='purchase_order_list'),
    path('orders/add/', views.purchase_order_create, name='purchase_order_create'),
    path('orders/<int:order_id>/', views.purchase_order_detail, name='purchase_order_detail'),
    path('orders/<int:order_id>/approve/', views.purchase_order_approve, name='purchase_order_approve'),
    path('orders/<int:order_id>/receive/', views.purchase_order_receive, name='purchase_order_receive'),

    # Dispensing
    path('dispensing/', views.dispensing_list, name='dispensing_list'),
    path('dispensing/new/', views.dispensing_create, name='dispensing_create'),

    # Stock Adjustments
    path('adjustments/', views.stock_adjustment_list, name='adjustment_list'),
    path('adjustments/new/', views.stock_adjustment_create, name='adjustment_create'),

    # Audit & Reports
    path('audit/', views.audit_log_list, name='audit_log_list'),
    path('reports/compliance/', views.compliance_report, name='compliance_report'),
    path('reports/cost/', views.cost_analysis, name='cost_analysis'),

    # AJAX
    path('api/batches/<int:medicine_id>/', views.api_batches_for_medicine, name='api_batches_for_medicine'),
]
