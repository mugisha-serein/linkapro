set -o errexit

pip install -r requirements/base.txt -r requirements/production.txt -r requirements/fastapi.txt -r requirements/test.txt

python manage.py collectstatic --no-input

python manage.py migrate --no-input