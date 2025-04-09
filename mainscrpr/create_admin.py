"""
Script to create an admin user.
Usage: python manage.py shell < create_admin.py
"""

from django.contrib.auth.models import User
from django.db.utils import IntegrityError

try:
    # Create superuser if it doesn't exist
    if not User.objects.filter(username='qiyas').exists():
        User.objects.create_superuser('qiyas', 'admin@example.com', 'qiyas')
        print("Admin user 'qiyas' created successfully.")
    else:
        print("Admin user 'qiyas' already exists.")
except IntegrityError:
    print("Error creating admin user: User 'qiyas' already exists.")
except Exception as e:
    print(f"Error creating admin user: {e}")
