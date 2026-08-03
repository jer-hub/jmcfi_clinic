from django.conf import settings
from django.db import models


class ConcernRecord(models.Model):
    class AffiliationType(models.TextChoices):
        CATALOG = 'catalog', 'Catalog college/department'
        EMPLOYEE = 'employee', 'Employee'
        OTHERS = 'others', 'Others'

    date = models.DateField()
    time = models.TimeField()
    patient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='concern_records',
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    affiliation_type = models.CharField(
        max_length=20,
        choices=AffiliationType.choices,
        default=AffiliationType.CATALOG,
    )
    college_department = models.ForeignKey(
        'core.CollegeDepartment',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='concern_records',
    )
    department_other = models.CharField(
        max_length=200,
        blank=True,
        help_text='Used when affiliation is Others.',
    )
    course_program = models.ForeignKey(
        'core.CourseProgram',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='concern_records',
    )
    year_level = models.ForeignKey(
        'core.YearLevelOption',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='concern_records',
    )
    concerns = models.TextField()
    management_treatment = models.TextField(
        verbose_name='Management/treatment rendered',
    )
    disposition = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='concern_records_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-time']
        verbose_name = 'Concern record'
        verbose_name_plural = 'Concern records'

    def __str__(self):
        return f"{self.full_name} — {self.date}"

    @property
    def full_name(self):
        parts = [self.last_name, self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        return ', '.join(p for p in parts if p)

    @property
    def display_name(self):
        middle = f" {self.middle_name}" if self.middle_name else ''
        return f"{self.first_name}{middle} {self.last_name}".strip()

    @property
    def department_display(self):
        other = (self.department_other or '').strip()
        if other:
            return other
        if self.college_department_id:
            return self.college_department.name
        if self.affiliation_type == self.AffiliationType.OTHERS:
            return 'Others'
        if self.affiliation_type == self.AffiliationType.EMPLOYEE:
            return 'Employee'
        return ''

    @property
    def academic_label(self):
        segments = [self.department_display] if self.department_display else []
        if (
            self.affiliation_type == self.AffiliationType.CATALOG
            and self.course_program_id
        ):
            segments.append(self.course_program.name)
        if (
            self.affiliation_type == self.AffiliationType.CATALOG
            and self.year_level_id
        ):
            segments.append(self.year_level.name)
        return ' • '.join(segments)
