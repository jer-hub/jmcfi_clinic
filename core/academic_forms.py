"""Forms for academic catalog admin settings."""

from django import forms

from .form_widgets import CHECKBOX_CLASS, INPUT_CLASS
from .models import CollegeDepartment, CourseProgram, YearLevelOption


class CollegeDepartmentForm(forms.ModelForm):
    class Meta:
        model = CollegeDepartment
        fields = ['name', 'course_optional', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'College or department name'}),
            'course_optional': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        }

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if not name:
            raise forms.ValidationError('Name is required.')
        qs = CollegeDepartment.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A college/department with this name already exists.')
        return name


class CourseProgramForm(forms.ModelForm):
    class Meta:
        model = CourseProgram
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Course or program name'}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        }

    def __init__(self, *args, college=None, **kwargs):
        self.college = college
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if not name:
            raise forms.ValidationError('Name is required.')
        if not self.college:
            return name
        qs = CourseProgram.objects.filter(
            college_department=self.college,
            name__iexact=name,
        )
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('This course/program already exists for the selected college.')
        return name


class YearLevelOptionForm(forms.ModelForm):
    class Meta:
        model = YearLevelOption
        fields = ['name', 'sort_order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Year level label'}),
            'sort_order': forms.NumberInput(attrs={'class': INPUT_CLASS, 'min': 0, 'max': 32767}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        }

    def __init__(self, *args, college=None, **kwargs):
        self.college = college
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if not name:
            raise forms.ValidationError('Name is required.')
        if not self.college:
            return name
        qs = YearLevelOption.objects.filter(
            college_department=self.college,
            name__iexact=name,
        )
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('This year level already exists for the selected college.')
        return name
