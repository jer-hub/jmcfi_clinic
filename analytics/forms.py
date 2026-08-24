from django import forms

from core.academic_catalog import patient_catalog_context
from core.models import YearLevelOption

from .models import FinancialRecord, ComplianceReport


def _year_level_choices():
    names = YearLevelOption.objects.filter(is_active=True).values_list('name', flat=True).distinct()
    return sorted(set(names))

# Standard Tailwind widget classes matching the rest of the project
INPUT_CSS = (
    'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm '
    'placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 '
    'focus:border-primary-500 sm:text-sm'
)
SELECT_CSS = INPUT_CSS
TEXTAREA_CSS = INPUT_CSS + ' resize-y'
COMPACT_SELECT = 'form-select'


class DateRangeFilterForm(forms.Form):
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': INPUT_CSS}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': INPUT_CSS}),
    )


class AcademicAnalyticsFilterForm(forms.Form):
    department = forms.ChoiceField(
        required=False,
        label='Department',
        choices=[],
        widget=forms.Select(attrs={'class': COMPACT_SELECT}),
    )
    course = forms.ChoiceField(
        required=False,
        label='Program',
        choices=[],
        widget=forms.Select(attrs={'class': COMPACT_SELECT}),
    )
    year_level = forms.ChoiceField(
        required=False,
        label='Year level',
        choices=[],
        widget=forms.Select(attrs={'class': COMPACT_SELECT}),
    )
    date_from = forms.DateField(
        required=False,
        label='From',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-input form-input--compact w-full min-w-[9.5rem]',
        }),
    )
    date_to = forms.DateField(
        required=False,
        label='To',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-input form-input--compact w-full min-w-[9.5rem]',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        catalog = patient_catalog_context()
        dept_choices = [('', 'All departments')] + [
            (name, name) for name in catalog['college_options']
        ]
        course_choices = [('', 'All programs')] + [
            (name, name) for name in catalog['course_options']
        ]
        year_choices = [('', 'All year levels')] + [
            (name, name) for name in _year_level_choices()
        ]
        self.fields['department'].choices = dept_choices
        self.fields['course'].choices = course_choices
        self.fields['year_level'].choices = year_choices


class HealthTrendFilterForm(forms.Form):
    illness_category = forms.CharField(
        required=False,
        label='Illness category',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Filter diagnoses…',
        }),
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
    department = forms.ChoiceField(
        required=False,
        label='Department filter',
        choices=[],
        widget=forms.Select(attrs={'class': COMPACT_SELECT}),
    )
    course = forms.ChoiceField(
        required=False,
        label='Program filter',
        choices=[],
        widget=forms.Select(attrs={'class': COMPACT_SELECT}),
    )
    year_level = forms.ChoiceField(
        required=False,
        label='Year level filter',
        choices=[],
        widget=forms.Select(attrs={'class': COMPACT_SELECT}),
    )

    class Meta:
        model = ComplianceReport
        fields = ['report_type', 'title', 'description', 'period_start', 'period_end', 'status']
        widgets = {
            'report_type': forms.Select(attrs={'class': COMPACT_SELECT}),
            'title': forms.TextInput(attrs={'class': INPUT_CSS}),
            'description': forms.Textarea(attrs={'class': TEXTAREA_CSS, 'rows': 3}),
            'period_start': forms.DateInput(attrs={'type': 'date', 'class': INPUT_CSS}),
            'period_end': forms.DateInput(attrs={'type': 'date', 'class': INPUT_CSS}),
            'status': forms.Select(attrs={'class': COMPACT_SELECT}),
        }

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('department'):
            cleaned['course'] = ''
            cleaned['year_level'] = ''
        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        catalog = patient_catalog_context()
        self.fields['department'].choices = [('', 'All departments')] + [
            (n, n) for n in catalog['college_options']
        ]
        self.fields['course'].choices = [('', 'All programs')] + [
            (n, n) for n in catalog['course_options']
        ]
        self.fields['year_level'].choices = [('', 'All year levels')] + [
            (n, n) for n in _year_level_choices()
        ]


class ExportForm(forms.Form):
    REPORT_CHOICES = [
        ('appointments', 'Appointments'),
        ('medical_records', 'Medical Records'),
        ('financial', 'Financial Records'),
        ('health_trends', 'Health Trends'),
        ('demographics', 'Patient Demographics'),
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
