.PHONY: install migrate test run seed superuser

install:
	.venv/bin/pip install -r requirements.txt

migrate:
	.venv/bin/python manage.py migrate

test:
	.venv/bin/python manage.py test

run:
	.venv/bin/python manage.py runserver 8000

seed:
	.venv/bin/python manage.py seed_demo_data

superuser:
	.venv/bin/python manage.py createsuperuser
