import os
from pathlib import Path
from django.core.wsgi import get_wsgi_application

# Load .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_app.settings.production')

application = get_wsgi_application()