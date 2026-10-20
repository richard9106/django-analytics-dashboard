from django.test import SimpleTestCase
from django.core.exceptions import ImproperlyConfigured
from .storage_config import cloud_storage_settings
from ops.backup_storage import destination


class CloudStorageTests(SimpleTestCase):
    def test_native_s3_uses_iam_role_without_source_endpoint_or_static_keys(self):
        settings = cloud_storage_settings({'DJANGO_STORAGE_BACKEND':'s3','AWS_STORAGE_BUCKET_NAME':'fictional-documents','AWS_S3_REGION_NAME':'us-east-1','AWS_ACCESS_KEY_ID':'','AWS_SECRET_ACCESS_KEY':''})
        self.assertIsNone(settings['AWS_ACCESS_KEY_ID'])
        self.assertIsNone(settings['AWS_SECRET_ACCESS_KEY'])
        self.assertIsNone(settings['AWS_S3_ENDPOINT_URL'])
        self.assertEqual(settings['AWS_S3_ADDRESSING_STYLE'],'virtual')

    def test_r2_configuration_is_preserved(self):
        settings=cloud_storage_settings({'DJANGO_STORAGE_BACKEND':'r2','AWS_STORAGE_BUCKET_NAME':'fictional','AWS_S3_ENDPOINT_URL':'https://fictional.r2.cloudflarestorage.com','AWS_ACCESS_KEY_ID':'synthetic','AWS_SECRET_ACCESS_KEY':'synthetic-secret'})
        self.assertEqual(settings['AWS_S3_REGION_NAME'],'auto')
        self.assertEqual(settings['AWS_S3_ADDRESSING_STYLE'],'path')

    def test_migration_rejects_leftover_source_endpoint_or_partial_credentials(self):
        base={'DJANGO_STORAGE_BACKEND':'s3','AWS_STORAGE_BUCKET_NAME':'fictional'}
        for addition in [{'AWS_S3_ENDPOINT_URL':'https://source.invalid'}, {'AWS_ACCESS_KEY_ID':'synthetic'}, {'AWS_S3_REGION_NAME':'auto'}]:
            with self.assertRaises(ImproperlyConfigured):cloud_storage_settings(dict(base,**addition))

    def test_backup_can_use_separate_bucket_and_instance_role(self):
        bucket, options=destination({'BACKUP_S3_BUCKET':'fictional-backups','AWS_STORAGE_BUCKET_NAME':'fictional-documents','AWS_S3_REGION_NAME':'us-east-1'})
        self.assertEqual(bucket,'fictional-backups')
        self.assertNotIn('aws_access_key_id',options)
        self.assertNotIn('endpoint_url',options)

    def test_legacy_backup_destination_remains_compatible(self):
        bucket, options=destination({'AWS_STORAGE_BUCKET_NAME':'fictional-r2','AWS_S3_ENDPOINT_URL':'https://source.invalid','AWS_S3_REGION_NAME':'auto','AWS_ACCESS_KEY_ID':'synthetic','AWS_SECRET_ACCESS_KEY':'synthetic-secret'})
        self.assertEqual(bucket,'fictional-r2')
        self.assertEqual(options['endpoint_url'],'https://source.invalid')

    def test_backup_does_not_silently_send_to_r2_after_bucket_migration(self):
        with self.assertRaises(ValueError):destination({'BACKUP_S3_BUCKET':'fictional-backups','AWS_S3_ENDPOINT_URL':'https://source.invalid','AWS_S3_REGION_NAME':'us-east-1'})
