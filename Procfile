web: gunicorn eso_backend.wsgi --log-file -
release: python manage.py migrate && python manage.py train_model
