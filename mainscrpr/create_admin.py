from django.contrib.auth.models import User

username = "qiyas"
password = "qiyas"
email = "qiyas@example.com"

if User.objects.filter(username=username).exists():
    print(f"Admin user '{username}' already exists.")
else:
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Admin user '{username}' created successfully.")