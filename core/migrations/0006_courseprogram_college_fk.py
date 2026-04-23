from django.db import migrations, models
import django.db.models.deletion


def populate_course_college_fk(apps, schema_editor):
    CourseProgram = apps.get_model('core', 'CourseProgram')
    CollegeDepartment = apps.get_model('core', 'CollegeDepartment')

    colleges = {
        obj.name: obj for obj in CollegeDepartment.objects.all()
    }

    # Fallback college if mapping misses
    fallback = colleges.get('College of Arts and Sciences')
    if fallback is None:
        fallback = CollegeDepartment.objects.order_by('id').first()

    mapping = {
        'BS Nursing': 'College of Nursing',
        'BS Midwifery': 'College of Nursing',
        'BS Medical Technology': 'College of Allied Health Sciences',
        'BS Physical Therapy': 'College of Allied Health Sciences',
        'BS Information Technology': 'College of Information Technology',
        'BS Psychology': 'College of Arts and Sciences',
        'BS Education': 'College of Education',
    }

    for course in CourseProgram.objects.all():
        college_name = mapping.get(course.name)
        college = colleges.get(college_name) if college_name else None
        if college is None:
            college = fallback
        if college is not None:
            course.college_department_id = college.id
            course.save(update_fields=['college_department'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_courseprogram_collegedepartment'),
    ]

    operations = [
        migrations.AddField(
            model_name='courseprogram',
            name='college_department',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='course_programs',
                to='core.collegedepartment',
            ),
        ),
        migrations.RunPython(populate_course_college_fk, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='courseprogram',
            name='college_department',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='course_programs',
                to='core.collegedepartment',
            ),
        ),
        migrations.AlterField(
            model_name='courseprogram',
            name='name',
            field=models.CharField(max_length=120),
        ),
        migrations.AlterUniqueTogether(
            name='courseprogram',
            unique_together={('college_department', 'name')},
        ),
    ]
