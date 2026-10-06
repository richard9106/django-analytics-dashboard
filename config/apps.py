from django_summernote.apps import DjangoSummernoteConfig


class SummernoteConfig(DjangoSummernoteConfig):
    # The published Summernote migrations use AutoField. Do not inherit the
    # application's BigAutoField default and generate migrations in site-packages.
    default_auto_field = 'django.db.models.AutoField'
