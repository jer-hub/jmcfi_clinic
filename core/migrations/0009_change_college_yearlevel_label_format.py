from django.db import migrations


TERTIARY_YEAR_LEVELS = [
    '1st Year',
    '2nd Year',
    '3rd Year',
    '4th Year',
]

IBED_DEPARTMENTS = {
    'IBED - Primary',
    'IBED - Junior High School',
    'IBED - Senior High School',
}


def apply_college_yearlevel_format(apps, schema_editor):
    CollegeDepartment = apps.get_model('core', 'CollegeDepartment')
    YearLevelOption = apps.get_model('core', 'YearLevelOption')

    colleges = CollegeDepartment.objects.filter(is_active=True).exclude(name__in=IBED_DEPARTMENTS)

    for college in colleges:
        # Keep only 1st-4th Year labels for tertiary colleges.
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
        ('core', '0008_adjust_college_year_levels_to_1_to_4'),
    ]

    operations = [
        migrations.RunPython(apply_college_yearlevel_format, migrations.RunPython.noop),
    ]
