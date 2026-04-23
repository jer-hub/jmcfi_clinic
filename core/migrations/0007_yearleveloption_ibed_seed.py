from django.db import migrations, models
import django.db.models.deletion


def seed_year_levels(apps, schema_editor):
    CollegeDepartment = apps.get_model('core', 'CollegeDepartment')
    YearLevelOption = apps.get_model('core', 'YearLevelOption')

    tertiary_levels = [
        '1st Year',
        '2nd Year',
        '3rd Year',
        '4th Year',
        '5th Year',
        'Graduate',
    ]

    ibed_level_map = {
        'IBED - Primary': [
            'Grade 1',
            'Grade 2',
            'Grade 3',
            'Grade 4',
            'Grade 5',
            'Grade 6',
        ],
        'IBED - Junior High School': [
            'Grade 7',
            'Grade 8',
            'Grade 9',
            'Grade 10',
        ],
        'IBED - Senior High School': [
            'Grade 11',
            'Grade 12',
        ],
    }

    # Ensure IBED departments exist and are active.
    for dept_name in ibed_level_map:
        department, _ = CollegeDepartment.objects.get_or_create(name=dept_name)
        if not department.is_active:
            department.is_active = True
            department.save(update_fields=['is_active'])

    for department in CollegeDepartment.objects.filter(is_active=True):
        level_names = ibed_level_map.get(department.name, tertiary_levels)
        for index, level_name in enumerate(level_names, start=1):
            YearLevelOption.objects.update_or_create(
                college_department=department,
                name=level_name,
                defaults={
                    'sort_order': index,
                    'is_active': True,
                },
            )


def unseed_year_levels(apps, schema_editor):
    YearLevelOption = apps.get_model('core', 'YearLevelOption')
    YearLevelOption.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_courseprogram_college_fk'),
    ]

    operations = [
        migrations.CreateModel(
            name='YearLevelOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('college_department', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='year_levels', to='core.collegedepartment')),
            ],
            options={
                'ordering': ['college_department__name', 'sort_order', 'name'],
                'unique_together': {('college_department', 'name')},
            },
        ),
        migrations.RunPython(seed_year_levels, unseed_year_levels),
    ]
