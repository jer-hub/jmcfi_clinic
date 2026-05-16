from django import forms

from .models import FinancialRecord, ComplianceReport, HealthTrendRecord


def health_trend_term_choices():
    """School-term options from stored trend records only."""
    sem_labels = dict(HealthTrendRecord.SEMESTER_CHOICES)
    pairs = HealthTrendRecord.objects.values_list('academic_year', 'semester').distinct()
    return [
        (
            f'{academic_year}|{semester}',
            f'{academic_year} · {sem_labels.get(semester, semester)}',
        )
        for academic_year, semester in sorted(pairs, reverse=True)
    ]


def split_health_trend_term(term_value):
    """Return (academic_year, semester) from a combined term value, or ('', '')."""
    if not term_value or '|' not in term_value:
        return '', ''
    academic_year, semester = term_value.split('|', 1)
    return academic_year.strip(), semester.strip()

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
    term = forms.ChoiceField(
        required=False,
        label='School term',
        choices=[],
        widget=forms.Select(attrs={'class': 'form-input form-input--compact'}),
    )
    illness_category = forms.CharField(
        required=False,
        label='Illness category',
        widget=forms.TextInput(attrs={
            'class': 'form-input form-input--compact',
            'placeholder': 'Filter diagnoses…',
        }),
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
        data = args[0] if args else None
        if data is not None and not data.get('term'):
            legacy_year = (data.get('academic_year') or '').strip()
            legacy_sem = (data.get('semester') or '').strip()
            if legacy_year and legacy_sem:
                data = data.copy()
                data['term'] = f'{legacy_year}|{legacy_sem}'
                args = (data,) + args[1:]
        super().__init__(*args, **kwargs)
        self.fields['term'].choices = [('', 'All terms')] + health_trend_term_choices()


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
