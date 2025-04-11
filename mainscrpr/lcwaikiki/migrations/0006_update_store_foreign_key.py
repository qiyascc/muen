from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('lcwaikiki', '0005_city_product_productsize_store_sizestorestock'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Drop the existing foreign key constraint
            ALTER TABLE lcwaikiki_store DROP CONSTRAINT IF EXISTS lcwaikiki_store_city_id_a0669b8f_fk_lcwaikiki;
            
            -- Create the new foreign key constraint pointing to the lcwaikiki_city table
            ALTER TABLE lcwaikiki_store 
            ADD CONSTRAINT lcwaikiki_store_city_id_fk_city 
            FOREIGN KEY (city_id) 
            REFERENCES lcwaikiki_city(city_id);
            """,
            reverse_sql="""
            -- Drop the new foreign key constraint
            ALTER TABLE lcwaikiki_store DROP CONSTRAINT IF EXISTS lcwaikiki_store_city_id_fk_city;
            
            -- Recreate the original foreign key constraint
            ALTER TABLE lcwaikiki_store 
            ADD CONSTRAINT lcwaikiki_store_city_id_a0669b8f_fk_lcwaikiki 
            FOREIGN KEY (city_id) 
            REFERENCES lcwaikiki_cityconfiguration(city_id);
            """
        ),
    ]