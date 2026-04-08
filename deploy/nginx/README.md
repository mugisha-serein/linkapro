# Nginx Reverse Proxy + SSL Deployment for Linkapro

## Overview

This folder contains a production-ready Nginx configuration for reverse proxying requests to the Django application and terminating SSL.

## What it does

- Redirects HTTP (`:80`) to HTTPS
- Terminates TLS on Nginx
- Serves static files from `/static/`
- Serves media files from `/media/`
- Proxies application requests to the upstream Django worker on `127.0.0.1:8000`

## Deployment steps

1. Update Django settings:
   - Set `DEBUG = False`
   - Add your domain to `ALLOWED_HOSTS`, e.g. `['linkapro.example.com']`
   - Add production static/media settings:
     ```python
     STATIC_URL = '/static/'
     STATIC_ROOT = BASE_DIR / 'staticfiles'
     MEDIA_URL = '/media/'
     MEDIA_ROOT = BASE_DIR / 'media'
     SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
     SECURE_SSL_REDIRECT = True
     SESSION_COOKIE_SECURE = True
     CSRF_COOKIE_SECURE = True
     CSRF_TRUSTED_ORIGINS = ['https://linkapro.example.com']
     ```

2. Collect static files:
   ```bash
   python manage.py collectstatic --noinput
   ```

3. Configure Gunicorn (or another WSGI server):
   ```bash
   gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 4
   ```

4. Install the Nginx site config:
   ```bash
   sudo ln -s /etc/nginx/sites-available/linkapro.conf /etc/nginx/sites-enabled/linkapro.conf
   sudo nginx -t
   sudo systemctl reload nginx
   ```

5. Add TLS certificates:
   - Use Let's Encrypt:
     ```bash
     sudo certbot --nginx -d linkapro.example.com
     ```
   - Or update `ssl_certificate` / `ssl_certificate_key` in `deploy/nginx/linkapro.conf` to your certificate paths.

## Notes

- Change `linkapro.example.com` to your real domain.
- If your Django app listens on a different port or socket, update the `upstream linkapro_app` block.
- If you use ASGI/uvicorn instead of Gunicorn, point the upstream at the ASGI server port.
