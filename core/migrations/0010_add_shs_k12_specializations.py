from django.db import migrations


SHS_DEPARTMENT_CANDIDATES = [
    'IBED - Senior High School',
    'IBED - Senior Highschool',
]

K12_SPECIALIZATIONS = [
    'K-12 STEM',
    'K-12 ABM',
    'K-12 HUMSS',
    'K-12 GAS',
    'K-12 TVL',
    'K-12 Arts and Design',
    'K-12 Sports',
]


def seed_shs_k12_specializations(apps, schema_editor):
    CollegeDepartment = apps.get_model('core', 'CollegeDepartment')
    CourseProgram = apps.get_model('core', 'CourseProgram')

    department = None
    for name in SHS_DEPARTMENT_CANDIDATES:
        department = CollegeDepartment.objects.filter(name=name).first()
        if department:
            break

    if department is None:
        department = CollegeDepartment.objects.create(
            name='IBED - Senior High School',
            is_active=True,
        )

    if not department.is_active:
        department.is_active = True
        department.save(update_fields=['is_active'])

    for name in K12_SPECIALIZATIONS:
        CourseProgram.objects.update_or_create(
            college_department=department,
            name=name,
            defaults={'is_active': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_change_college_yearlevel_label_format'),
    ]

    operations = [
        migrations.RunPython(seed_shs_k12_specializations, migrations.RunPython.noop),
    ]
