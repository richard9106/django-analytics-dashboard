"""Capture encrypted NuviaMy configuration outside the VPS; run on the custodian's computer.

Private recovery keys are generated/stored locally and never uploaded. SSH only
streams ciphertext. This is a configuration snapshot, not a database/files backup.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import tarfile


def checked(args, **kwargs):
    result = subprocess.run(args, capture_output=True, timeout=120, **kwargs)
    if result.returncode:
        raise RuntimeError('Recovery operation failed; no secret output is displayed.')
    return result.stdout


def ensure_recipient(key_dir):
    key_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(key_dir, 0o700)
    key, cert = key_dir / 'recovery-private.pem', key_dir / 'recovery-public.pem'
    if key.exists() != cert.exists():
        raise RuntimeError('Incomplete existing key pair; do not overwrite it.')
    if not key.exists():
        old = os.umask(0o077)
        try:
            checked(['openssl', 'req', '-x509', '-newkey', 'rsa:3072', '-nodes', '-days', '3650',
                     '-subj', '/CN=NuviaMy recovery recipient', '-keyout', str(key), '-out', str(cert)])
        finally:
            os.umask(old)
    os.chmod(key, 0o600)
    os.chmod(cert, 0o600)
    return key, cert


def inspect_bundle(ciphertext, key):
    plain = checked(['openssl', 'cms', '-decrypt', '-binary', '-inform', 'DER', '-inkey', str(key)], input=ciphertext)
    with tarfile.open(fileobj=io.BytesIO(plain), mode='r:gz') as archive:
        members = archive.getmembers()
        if any(not m.isfile() or Path(m.name).is_absolute() or '..' in Path(m.name).parts for m in members):
            raise RuntimeError('Unexpected archive entry; nothing was extracted.')
        member = next(m for m in members if m.name == '.env')
        contents = archive.extractfile(member).read()
        required = (b'DJANGO_SECRET_KEY=', b'FIELD_ENCRYPTION_KEY=', b'BACKUP_ENCRYPTION_PASSPHRASE=')
        if not all(name in contents for name in required):
            raise RuntimeError('Required configuration entries are missing.')
        return {'entry_count': len(members), 'configuration_keys_present': True,
                'archive_sha256': hashlib.sha256(plain).hexdigest()}


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--key-dir', type=Path, default=Path.home() / '.local/share/nuviamy-recovery')
    args = parser.parse_args()
    key, cert = ensure_recipient(args.key_dir)
    remote_cert = '/root/.config/nuviamy/recovery-recipient.pem'
    checked(['ssh', args.host, 'umask 077; mkdir -p /root/.config/nuviamy; cat > ' + remote_cert], input=cert.read_bytes())
    files = ['etc/nginx/sites-enabled/django-analytics-dashboard',
             'etc/systemd/system/nuviamy-postgres-backup.service', 'etc/systemd/system/nuviamy-postgres-backup.timer',
             'etc/systemd/system/nuviamy-appointment-reminders.service', 'etc/systemd/system/nuviamy-appointment-reminders.timer']
    tar_args = ['tar', '--dereference', '-czf', '-', '--directory=/home/deploy/apps/django-analytics-dashboard',
                '.env', 'docker-compose.yml', '--directory=/', *files,
                '--directory=/root/.config/nuviamy', 'stripe-live.env']
    command = shlex.join(tar_args) + ' | ' + shlex.join([
        'openssl', 'cms', '-encrypt', '-aes-256-gcm', '-binary', '-outform', 'DER',
        '-recip', remote_cert, '-keyopt', 'rsa_padding_mode:oaep'])
    ciphertext = checked(['ssh', args.host, 'bash -o pipefail -c ' + shlex.quote(command)])
    proof = inspect_bundle(ciphertext, key)
    tampered = ciphertext[:-1] + bytes([ciphertext[-1] ^ 1])
    try:
        inspect_bundle(tampered, key)
    except RuntimeError:
        proof['tamper_rejected'] = True
    else:
        raise RuntimeError('Authenticated decryption did not reject alteration.')
    args.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(args.output_dir, 0o700)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    bundle = args.output_dir / ('nuviamy-config-' + stamp + '.cms')
    fd = os.open(bundle, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(ciphertext)
    proof.update({'created_at':stamp, 'ciphertext_sha256':hashlib.sha256(ciphertext).hexdigest(),
                  'bundle':str(bundle), 'private_key_local_only':True, 'plaintext_extracted':False})
    manifest = bundle.with_suffix('.json')
    fd = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(proof, f, indent=2)
    print(json.dumps(proof))


if __name__ == '__main__':
    run()
