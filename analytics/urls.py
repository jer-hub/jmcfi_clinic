from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Main dashboard
    path('', views.analytics_dashboard, name='dashboard'),

    # 1. Health Trend Analysis
    path('health-trends/', views.health_trends, name='health_trends'),

    # 2. Predictive Analytics
    path('predictive/', views.predictive_analytics, name='predictive_analytics'),
    path('predictive/generate/', views.generate_predictive_insight, name='generate_insight'),

    # 3. Resource Utilization
    path('resources/', views.resource_utilization, name='resource_utilization'),

    # 4. Compliance & Accreditation
    path('compliance/', views.compliance_reports, name='compliance_reports'),
    path('compliance/generate/', views.generate_compliance_report, name='generate_compliance_report'),
    path('compliance/<int:pk>/', views.compliance_report_detail, name='compliance_report_detail'),

    # 5. Population Health
    path('population/', views.population_health, name='population_health'),

    # 6. Financial & Cost Analysis
    path('financial/', views.financial_overview, name='financial_overview'),
    path('financial/create/', views.financial_record_create, name='financial_record_create'),

    # 7. Academic Integration
    path('academic/', views.academic_correlation, name='academic_correlation'),

    # Export
    path('export/', views.export_report, name='export_report'),

    # Chart data API
    path('api/chart-data/', views.chart_data_api, name='chart_data_api'),
]
