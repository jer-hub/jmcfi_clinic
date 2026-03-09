from django.db import models
from django.conf import settings


class HealthTrendRecord(models.Model):
    """Aggregated health trend data per semester/period."""
    SEMESTER_CHOICES = [
        ('1st', '1st Semester'),
        ('2nd', '2nd Semester'),
        ('summer', 'Summer'),
    ]

    academic_year = models.CharField(max_length=20, help_text='e.g. 2025-2026')
    semester = models.CharField(max_length=10, choices=SEMESTER_CHOICES)
    illness_category = models.CharField(max_length=100, help_text='e.g. Flu, Dengue, Stress')
    case_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-academic_year', 'semester', '-case_count']
        unique_together = ['academic_year', 'semester', 'illness_category']

    def __str__(self):
        return f"{self.illness_category} – {self.academic_year} {self.get_semester_display()}"


class PredictiveInsight(models.Model):
    """AI-generated predictive insights for clinic operations."""
    INSIGHT_TYPES = [
        ('medicine_demand', 'Medicine Demand Forecast'),
        ('staff_workload', 'Staff Workload Prediction'),
        ('peak_hours', 'Peak Hours Analysis'),
        ('outbreak_risk', 'Outbreak Risk Alert'),
    ]
    RISK_LEVELS = [
        ('low', 'Low'),
        ('moderate', 'Moderate'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    insight_type = models.CharField(max_length=30, choices=INSIGHT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    data_json = models.JSONField(default=dict, blank=True, help_text='Raw prediction data')
    risk_level = models.CharField(max_length=10, choices=RISK_LEVELS, default='low')
    period_start = models.DateField()
    period_end = models.DateField()
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='generated_insights'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_insight_type_display()} – {self.title}"


class ResourceUtilization(models.Model):
    """Daily resource utilization snapshot."""
    date = models.DateField(unique=True)
    total_consultations = models.PositiveIntegerField(default=0)
    avg_consultation_minutes = models.FloatField(default=0)
    patient_throughput = models.PositiveIntegerField(default=0, help_text='Patients served')
    staff_on_duty = models.PositiveIntegerField(default=0)
    peak_hour = models.PositiveSmallIntegerField(null=True, blank=True, help_text='0-23')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Resource Utilization – {self.date}"

    @property
    def efficiency_score(self):
        """Simple efficiency metric: throughput / staff (if > 0)."""
        if self.staff_on_duty:
            return round(self.patient_throughput / self.staff_on_duty, 1)
        return 0


class ComplianceReport(models.Model):
    """Generated compliance/accreditation reports."""
    REPORT_TYPES = [
        ('ched', 'CHED Report'),
        ('doh', 'DOH Report'),
        ('accreditation', 'University Accreditation'),
        ('data_privacy', 'Data Privacy Compliance'),
        ('custom', 'Custom Report'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('final', 'Final'),
        ('submitted', 'Submitted'),
    ]

    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    data_json = models.JSONField(default=dict, blank=True, help_text='Report data payload')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='compliance_reports'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_report_type_display()} – {self.title}"


class FinancialRecord(models.Model):
    """Clinic financial/cost tracking entries."""
    CATEGORY_CHOICES = [
        ('medicine', 'Medicine & Supplies'),
        ('equipment', 'Equipment'),
        ('staffing', 'Staffing Costs'),
        ('outsourced', 'Outsourced Services'),
        ('billing', 'Patient Billing'),
        ('insurance', 'Insurance Claims'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other'),
    ]

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_expense = models.BooleanField(default=True, help_text='True = expense, False = income')
    date = models.DateField()
    reference_number = models.CharField(max_length=100, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='financial_records'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        kind = 'Expense' if self.is_expense else 'Income'
        return f"{kind}: {self.description} – ₱{self.amount:,.2f}"


class ExportLog(models.Model):
    """Track exported reports for audit."""
    FORMAT_CHOICES = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
    ]

    report_name = models.CharField(max_length=255)
    export_format = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    exported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='export_logs'
    )
    file_path = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.report_name} ({self.export_format}) – {self.created_at:%Y-%m-%d}"
