from django import forms
from django.contrib.auth import get_user_model

from core.academic_catalog import active_colleges_queryset
from core.models import CollegeDepartment, CourseProgram, YearLevelOption

from .models import ConcernRecord

_INPUT = (
    'block w-full px-3 py-2.5 border border-gray-300 rounded-lg shadow-sm '
    'focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 '
    'text-sm transition-colors bg-white'
)
_TEXTAREA = _INPUT + ' resize-y'

def _profile_for_user(user):
    if not user:
        return None
    return getattr(user, 'patient_profile', None) or getattr(user, 'staff_profile', None)


class ConcernRecordForm(forms.ModelForm):
    patient_user = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        required=False,
        widget=forms.HiddenInput(),
    )
    affiliation_type = forms.ChoiceField(
        choices=ConcernRecord.AffiliationType.choices,
        required=True,
        widget=forms.HiddenInput(),
        initial=ConcernRecord.AffiliationType.CATALOG,
    )
    department_other = forms.CharField(
        required=False,
        max_length=200,
        label='Specify department',
        widget=forms.TextInput(
            attrs={
                'class': _INPUT,
                'placeholder': 'Enter department or college not in the list…',
                'autocomplete': 'organization',
                'x-model': 'departmentOther',
                '@input': 'syncDepartmentOther()',
            }
        ),
    )

    class Meta:
        model = ConcernRecord
        fields = [
            'date',
            'time',
            'patient_user',
            'first_name',
            'last_name',
            'middle_name',
            'affiliation_type',
            'college_department',
            'department_other',
            'course_program',
            'year_level',
            'concerns',
            'management_treatment',
            'disposition',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'class': _INPUT, 'type': 'date'}),
            'time': forms.TimeInput(attrs={'class': _INPUT, 'type': 'time'}),
            'first_name': forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Last name'}),
            'middle_name': forms.TextInput(
                attrs={'class': _INPUT, 'placeholder': 'Middle name (optional)'}
            ),
            'college_department': forms.HiddenInput(),
            'course_program': forms.Select(attrs={'class': _INPUT}),
            'year_level': forms.Select(attrs={'class': _INPUT}),
            'concerns': forms.Textarea(
                attrs={'class': _TEXTAREA, 'rows': 4, 'placeholder': 'Describe the concern…'}
            ),
            'management_treatment': forms.Textarea(
                attrs={
                    'class': _TEXTAREA,
                    'rows': 4,
                    'placeholder': 'Management/treatment rendered…',
                }
            ),
            'disposition': forms.Textarea(
                attrs={'class': _TEXTAREA, 'rows': 3, 'placeholder': 'Disposition…'}
            ),
        }
        labels = {
            'college_department': 'Department / College',
            'course_program': 'Program',
            'year_level': 'Year level',
            'management_treatment': 'Management/treatment rendered',
        }
        help_texts = {
            'course_program': 'Filtered by selected college/department',
            'year_level': 'Filtered by selected college/department',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user_model = get_user_model()
        self.fields['patient_user'].queryset = user_model.objects.filter(is_active=True)

        college_qs = active_colleges_queryset()
        program_qs = CourseProgram.objects.select_related('college_department').filter(
            is_active=True,
            college_department__is_active=True,
        )
        year_qs = YearLevelOption.objects.select_related('college_department').filter(
            is_active=True,
            college_department__is_active=True,
        )

        instance = kwargs.get('instance')
        if instance and instance.pk and instance.college_department_id:
            current = CollegeDepartment.objects.filter(pk=instance.college_department_id)
            college_qs = (college_qs | current).distinct().order_by('name')
            if instance.course_program_id:
                program_qs = (
                    program_qs | CourseProgram.objects.filter(pk=instance.course_program_id)
                ).distinct()
            if instance.year_level_id:
                year_qs = (
                    year_qs | YearLevelOption.objects.filter(pk=instance.year_level_id)
                ).distinct()

        self.fields['college_department'].queryset = college_qs
        self.fields['college_department'].required = False
        self.fields['course_program'].queryset = program_qs.order_by(
            'college_department__name',
            'name',
        )
        self.fields['year_level'].queryset = year_qs.order_by(
            'college_department__name',
            'sort_order',
            'name',
        )
        self.fields['course_program'].label_from_instance = lambda obj: obj.name
        self.fields['year_level'].label_from_instance = lambda obj: obj.name
        self.fields['course_program'].empty_label = 'Select program'
        self.fields['year_level'].empty_label = 'Select year level'
        self.fields['middle_name'].required = False
        self.fields['course_program'].required = False
        self.fields['year_level'].required = False

        if instance and instance.pk:
            self.fields['affiliation_type'].initial = instance.affiliation_type
            self.fields['department_other'].initial = instance.department_other

    def clean(self):
        cleaned_data = super().clean()
        affiliation_type = cleaned_data.get('affiliation_type') or ConcernRecord.AffiliationType.CATALOG
        college_department = cleaned_data.get('college_department')
        department_other = (cleaned_data.get('department_other') or '').strip()
        course_program = cleaned_data.get('course_program')
        year_level = cleaned_data.get('year_level')
        patient_user = cleaned_data.get('patient_user')
        first_name = (cleaned_data.get('first_name') or '').strip()
        last_name = (cleaned_data.get('last_name') or '').strip()
        middle_name = (cleaned_data.get('middle_name') or '').strip()

        profile = _profile_for_user(patient_user)

        if patient_user:
            if not first_name:
                first_name = (patient_user.first_name or '').strip()
            if not last_name:
                last_name = (patient_user.last_name or '').strip()
            if not middle_name and profile:
                middle_name = (getattr(profile, 'middle_name', '') or '').strip()
            cleaned_data['first_name'] = first_name
            cleaned_data['last_name'] = last_name
            cleaned_data['middle_name'] = middle_name

        if not patient_user and (not first_name or not last_name):
            raise forms.ValidationError(
                'Select an existing user or provide at least first and last name.'
            )

        if affiliation_type == ConcernRecord.AffiliationType.EMPLOYEE:
            cleaned_data['course_program'] = None
            cleaned_data['year_level'] = None
            if department_other:
                # Employee whose workplace department is not in the catalog list.
                cleaned_data['college_department'] = None
                cleaned_data['department_other'] = department_other
            else:
                cleaned_data['department_other'] = ''
                if not college_department:
                    self.add_error(
                        'college_department',
                        'Select a college/department, or check Others to specify.',
                    )
        elif affiliation_type == ConcernRecord.AffiliationType.OTHERS:
            cleaned_data['college_department'] = None
            cleaned_data['course_program'] = None
            cleaned_data['year_level'] = None
            cleaned_data['department_other'] = department_other
            if not department_other:
                self.add_error(
                    'department_other',
                    'Specify the department when it is not in the list.',
                )
        else:
            cleaned_data['affiliation_type'] = ConcernRecord.AffiliationType.CATALOG
            cleaned_data['department_other'] = ''
            if not college_department:
                self.add_error(
                    'college_department',
                    'Select a college/department from the list, or check Others to specify.',
                )
            if college_department and course_program:
                if course_program.college_department_id != college_department.id:
                    self.add_error(
                        'course_program',
                        'Program must belong to the selected college/department.',
                    )
            if college_department and year_level:
                if year_level.college_department_id != college_department.id:
                    self.add_error(
                        'year_level',
                        'Year level must belong to the selected college/department.',
                    )

        return cleaned_data
