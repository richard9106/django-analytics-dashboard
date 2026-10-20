"""Prepare private migration configuration; never provision resources or change DNS."""
import argparse
import json
import os
from pathlib import Path
from dotenv import dotenv_values

REQUIRED=('DJANGO_SECRET_KEY','FIELD_ENCRYPTION_KEY','POSTGRES_DB','POSTGRES_PASSWORD',
          'POSTGRES_APP_USER','POSTGRES_APP_PASSWORD','POSTGRES_MIGRATION_USER','POSTGRES_MIGRATION_PASSWORD')


def prepare(source,destination,revision):
    values={k:v for k,v in dotenv_values(source).items() if v is not None}
    if any(not values.get(k) for k in REQUIRED):
        raise ValueError('Source configuration is incomplete; no files created.')
    import re
    if not re.fullmatch(r'[a-f0-9]{40}',revision):raise ValueError('Pin a full reviewed Git commit.')
    destination.mkdir(mode=0o700,parents=False,exist_ok=False)
    os.chmod(destination,0o700)
    def save(name,content):
        fd=os.open(destination/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:f.write(content)
    # Preserve the source bytes for explicit cutover review, not automatic activation.
    save('production-candidate.env',source.read_text())
    values['POSTGRES_DB']=values['POSTGRES_DB']+'_rehearsal'
    values['MIGRATION_REHEARSAL']='true'
    values.update(EMAIL_BACKEND='django.core.mail.backends.dummy.EmailBackend',SIGNUP_NOTIFICATION_EMAIL='',
        STRIPE_SECRET_KEY='',STRIPE_PUBLISHABLE_KEY='',STRIPE_WEBHOOK_SECRET='',STRIPE_LIVE_VERIFY_WEBHOOK_SECRET='',
        STRIPE_LIVE_VERIFY_NONCE='',SENTRY_DSN='',GOOGLE_OAUTH_CLIENT_ID='',GOOGLE_OAUTH_CLIENT_SECRET='',
        AWS_ACCESS_KEY_ID='',AWS_SECRET_ACCESS_KEY='',AWS_SESSION_TOKEN='',AWS_EC2_METADATA_DISABLED='true',
        AWS_S3_ENDPOINT_URL='',AWS_STORAGE_BUCKET_NAME='',DJANGO_STORAGE_BACKEND='',
        EMAIL_HOST_USER='',EMAIL_HOST_PASSWORD='',DJANGO_EMAIL_TWO_STEP_REQUIRED='false')
    # JSON strings are valid dotenv quoted values, including secrets with whitespace.
    save('rehearsal.env',''.join(k+'='+json.dumps(v)+'\n' for k,v in sorted(values.items())))
    save('manifest.json',json.dumps({'revision':revision,'environment_credentials_disabled':True,'database_oauth_isolation_required':True,
        'field_encryption_key_preserved':True,'production_configuration_not_activated':True},indent=2))
    return {'prepared':True,'environment_credentials_disabled':True,'database_oauth_isolation_required':True,'revision':revision}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-env',required=True,type=Path)
    parser.add_argument('--destination',required=True,type=Path)
    parser.add_argument('--revision',required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.source_env,args.destination,args.revision)))


if __name__=='__main__':main()
