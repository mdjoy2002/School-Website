from django.db import migrations


def ensure_student_user_id_column(apps, schema_editor):
    if schema_editor.connection.vendor != 'sqlite':
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute("PRAGMA table_info(students_student)")
        columns = {row[1] for row in cursor.fetchall()}
        if 'user_id' not in columns:
            cursor.execute(
                "ALTER TABLE students_student ADD COLUMN user_id INTEGER NULL REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED"
            )


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0008_remove_student_profile_ticker_studentticker'),
    ]

    operations = [
        migrations.RunPython(ensure_student_user_id_column, migrations.RunPython.noop),
    ]
