"""Upload an encrypted database backup, optionally to a separate native S3 bucket."""
import os
import sys
import boto3


def destination(env):
    bucket = env.get('BACKUP_S3_BUCKET') or env.get('AWS_STORAGE_BUCKET_NAME')
    if not bucket:
        raise ValueError('A backup bucket is required.')
    native = bool(env.get('BACKUP_S3_BUCKET'))
    options = {'region_name': env.get('AWS_S3_REGION_NAME') or ('us-east-1' if native else 'auto')}
    if native and options['region_name'] == 'auto':
        raise ValueError('Native S3 backups require an AWS region.')
    endpoint = env.get('AWS_S3_ENDPOINT_URL')
    if native and endpoint:
        raise ValueError('Remove the source R2 endpoint before using native S3 backups.')
    if endpoint:
        options['endpoint_url'] = endpoint
    access, secret = env.get('AWS_ACCESS_KEY_ID'), env.get('AWS_SECRET_ACCESS_KEY')
    if bool(access) != bool(secret):
        raise ValueError('Partial static credentials are not allowed.')
    if access:
        options.update(aws_access_key_id=access, aws_secret_access_key=secret)
        if env.get('AWS_SESSION_TOKEN'):
            options['aws_session_token'] = env['AWS_SESSION_TOKEN']
    return bucket, options


def main():
    bucket, options = destination(os.environ)
    path, key = sys.argv[1:]
    if not path.endswith('.gpg'):
        raise ValueError('Only encrypted GPG backups may be uploaded.')
    boto3.client('s3', **options).upload_file(path, bucket, key)
    print('Encrypted database backup uploaded.')


if __name__ == '__main__':
    main()
