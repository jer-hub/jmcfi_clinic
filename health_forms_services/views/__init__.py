# health_forms_services/views — re-exports everything
from .base import BaseFormListView, BaseFormDetailView, BaseFormEditView
from .forms_cbvs import (
    HealthProfileListView,
    HealthProfileDetailView,
    HealthProfileEditView,
)
from ._cbvs import (
    DentalListView, DentalDetailView, DentalEditView,
    PatientChartListView, PatientChartDetailView, PatientChartEditView,
    PrescriptionListView, PrescriptionDetailView, PrescriptionEditView,
    DentalServicesListView, DentalServicesDetailView, DentalServicesEditView,
)
# Re-export all original function-based views
from ._fbvs import *  # noqa: F403, F401
