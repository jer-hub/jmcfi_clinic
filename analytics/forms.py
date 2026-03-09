from django import forms
from .models import FinancialRecord, ComplianceReport, HealthTrendRecord

# Standard Tailwind widget classes matching the rest of the project
INPUT_CSS = (
    'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm '
    'placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 '
    'focus:border-primary-500 sm:text-sm'
)
SELECT_CSS = INPUT_CSS
TEXTAREA_CSS = INPUT_CSS + ' resize-y'


class DateRangeFilterForm(forms.Form):
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': INPUT_CSS}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': INPUT_CSS}),
    )


class HealthTrendFilterForm(forms.Form):
    academic_year = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': INPUT_CSS, 'placeholder': 'e.g. 2025-2026'}),
    )
    semester = forms.ChoiceField(
        required=False,
        choices=[('', 'All Semesters')] + HealthTrendRecord.SEMESTER_CHOICES,
        widget=forms.Select(attrs={'class': SELECT_CSS}),
    )
    illness_category = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': INPUT_CSS, 'placeholder': 'Search illness…'}),
    )


class FinancialRecordForm(forms.ModelForm):
    class Meta:
        model = FinancialRecord
        fields = [
            'category', 'description', 'amount', 'is_expense',
            'date', 'reference_number', 'notes',
        ]
        widgets = {
            'category': forms.Select(attrs={'class': SELECT_CSS}),
            'description': forms.TextInput(attrs={'class': INPUT_CSS}),
            'amount': forms.NumberInput(attrs={'class': INPUT_CSS, 'step': '0.01'}),
            'is_expense': forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': INPUT_CSS}),
            'reference_number': forms.TextInput(attrs={'class': INPUT_CSS}),
            'notes': forms.Textarea(attrs={'class': TEXTAREA_CSS, 'rows': 3}),
        }


class ComplianceReportForm(forms.ModelForm):
    class Meta:
        model = ComplianceReport
        fields = ['report_type', 'title', 'description', 'period_start', 'period_end', 'status']
        widgets = {
            'report_type': forms.Select(attrs={'class': SELECT_CSS}),
            'title': forms.TextInput(attrs={'class': INPUT_CSS}),
            'description': forms.Textarea(attrs={'class': TEXTAREA_CSS, 'rows': 3}),
            'period_start': forms.DateInput(attrs={'type': 'date', 'class': INPUT_CSS}),
            'period_end': forms.DateInput(attrs={'type': 'date', 'class': INPUT_CSS}),
            'status': forms.Select(attrs={'class': SELECT_CSS}),
        }


class ExportForm(forms.Form):
    REPORT_CHOICES = [
        ('appointments', 'Appointments'),
        ('medical_records', 'Medical Records'),
        ('financial', 'Financial Records'),
        ('health_trends', 'Health Trends'),
        ('demographics', 'Student Demographics'),
    ]
    report = forms.ChoiceField(
        choices=REPORT_CHOICES,
        widget=forms.Select(attrs={'class': SELECT_CSS}),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': INPUT_CSS}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': INPUT_CSS}),
    )
