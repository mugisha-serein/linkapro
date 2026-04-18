import os
import sys
import django
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "linkapro.django_app.settings.test")

# Initialize Django before running tests
django.setup()