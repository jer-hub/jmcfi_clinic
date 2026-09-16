"""Analytics views — re-exported for urls.py compatibility."""

from analytics.views.academic import academic_correlation
from analytics.views.api import admin_calendar_month_api, chart_data_api
from analytics.views.concerns import concerns_analysis
from analytics.views.compliance import (
    compliance_report_detail,
    compliance_reports,
    generate_compliance_report,
)
from analytics.views.dashboard import analytics_dashboard, render_analytics_dashboard
from analytics.views.export import export_report
from analytics.views.financial import financial_overview, financial_record_create
from analytics.views.health_trends import health_trends
from analytics.views.patient_charts import patient_charts_analysis
from analytics.views.population import population_health
from analytics.views.predictive import generate_predictive_insight, predictive_analytics
from analytics.views.utilization import resource_utilization

__all__ = [
    'academic_correlation',
    'admin_calendar_month_api',
    'analytics_dashboard',
    'chart_data_api',
    'compliance_report_detail',
    'compliance_reports',
    'concerns_analysis',
    'export_report',
    'financial_overview',
    'financial_record_create',
    'generate_compliance_report',
    'generate_predictive_insight',
    'health_trends',
    'patient_charts_analysis',
    'population_health',
    'predictive_analytics',
    'render_analytics_dashboard',
    'resource_utilization',
]
