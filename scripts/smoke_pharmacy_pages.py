import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django

django.setup()

from django.test import Client
from core.models import User


paths = [
    '/pharmacy/',
    '/pharmacy/medicines/',
    '/pharmacy/medicines/add/',
    '/pharmacy/categories/',
    '/pharmacy/categories/add/',
    '/pharmacy/batches/',
    '/pharmacy/batches/add/',
    '/pharmacy/suppliers/',
    '/pharmacy/suppliers/add/',
    '/pharmacy/orders/',
    '/pharmacy/orders/add/',
    '/pharmacy/dispensing/',
    '/pharmacy/dispensing/new/',
    '/pharmacy/adjustments/',
    '/pharmacy/adjustments/new/',
    '/pharmacy/audit/',
    '/pharmacy/reports/compliance/',
    '/pharmacy/reports/cost/',
]

user, _ = User.objects.get_or_create(
    email='smoke_admin@example.com',
    defaults={'role': 'admin', 'is_staff': True, 'is_superuser': True},
)

client = Client()
client.force_login(user)

failed = []

for path in paths:
    try:
        response = client.get(path, HTTP_HOST='127.0.0.1')
        print(f'{path} -> {response.status_code}')
        if response.status_code >= 400:
            failed.append((path, response.status_code))
    except Exception as exc:
        print(f'{path} -> EXCEPTION: {type(exc).__name__}: {exc}')
        failed.append((path, 'EXCEPTION'))

print('FAILED:', failed)
