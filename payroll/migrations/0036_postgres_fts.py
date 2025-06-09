from django.db import migrations, models
from django.contrib.postgres.operations import TrigramExtension

class Migration(migrations.Migration):
    dependencies = [
        ('payroll', '0035_reflect_aliases'),
    ]

    operations = [
        TrigramExtension(),
        
        # Add a column to store the full searchable name
        migrations.AddField(
            model_name='employer',
            name='search_name',
            field=models.CharField(default='default search name', max_length=510),
            preserve_default=False,
        ),
        
        # Populate the search_name field
        migrations.RunSQL(
            """
            UPDATE payroll_employer 
            SET search_name = CASE 
                WHEN parent_id IS NOT NULL THEN 
                    (SELECT p.name FROM payroll_employer p WHERE p.id = payroll_employer.parent_id) || ' ' || name
                ELSE name
            END;
            """,
            reverse_sql=""
        ),
        
        # Create the search indexes on the new column
        migrations.RunSQL(
            """
            CREATE INDEX payroll_employer_search_idx
            ON payroll_employer
            USING GIN (to_tsvector('english', search_name));
            """,
            reverse_sql="DROP INDEX payroll_employer_search_idx;"
        ),
        
        migrations.RunSQL(
            """
            CREATE INDEX payroll_person_search_idx
            ON payroll_person
            USING GIN (to_tsvector('english', first_name || ' ' || last_name));
            """,
            reverse_sql="DROP INDEX payroll_person_search_idx;"
        ),
        
        migrations.RunSQL(
            """
            CREATE INDEX payroll_employer_trigram_idx
            ON payroll_employer
            USING GIN (search_name gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX payroll_employer_trigram_idx;"
        ),
        
        migrations.RunSQL(
            """
            CREATE INDEX payroll_person_trigram_idx
            ON payroll_person
            USING GIN ((first_name || ' ' || last_name) gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX payroll_person_trigram_idx;"
        ),
    ]