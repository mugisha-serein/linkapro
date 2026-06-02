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

settings_module = 'django_app.settings.production' if 'RENDER_EXTERNAL_HOSTNAME' in os.environ else 'django_app.settings.development'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

application = get_wsgi_application()