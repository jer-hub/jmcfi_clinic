from django.db import migrations


TERTIARY_YEAR_LEVELS = [
    'Year 1',
    'Year 2',
    'Year 3',
    'Year 4',
]

IBED_DEPARTMENTS = {
    'IBED - Primary',
    'IBED - Junior High School',
    'IBED - Senior High School',
}


def apply_college_year_levels(apps, schema_editor):
    CollegeDepartment = apps.get_model('core', 'CollegeDepartment')
    YearLevelOption = apps.get_model('core', 'YearLevelOption')

    colleges = CollegeDepartment.objects.filter(is_active=True).exclude(name__in=IBED_DEPARTMENTS)

    for college in colleges:
        # Remove year levels outside Year 1..Year 4 for tertiary colleges.
        YearLevelOption.objects.filter(
            college_department=college,
        ).exclude(name__in=TERTIARY_YEAR_LEVELS).delete()

        for order, name in enumerate(TERTIARY_YEAR_LEVELS, start=1):
            YearLevelOption.objects.update_or_create(
                college_department=college,
                name=name,
                defaults={
                    'sort_order': order,
                    'is_active': True,
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_yearleveloption_ibed_seed'),
    ]

    operations = [
        migrations.RunPython(apply_college_year_levels, migrations.RunPython.noop),
    ]
