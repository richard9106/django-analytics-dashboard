"""Encrypted off-VPS document snapshots; restore only to a NEW isolated directory.

No remote objects or database records are changed. Each snapshot is independent
of later object deletion. Uses the same local recovery key as configuration copies.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import tarfile
from ops.offsite_config_backup import checked, ensure_recipient

MAX_SNAPSHOT_BYTES = 256 * 1024 * 1024
REMOTE_CAPTURE = r'''
import os, sys, io, json, hashlib, tarfile
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from apps.documents.models import ClientDocument
manifest=[]; total=0
with tarfile.open(fileobj=sys.stdout.buffer, mode='w|gz') as archive:
    for doc in ClientDocument.objects.exclude(file='').order_by('pk').iterator():
        with doc.file.open('rb') as source: data=source.read(25*1024*1024+1)
        total+=len(data)
        if len(data)>25*1024*1024 or total>200*1024*1024:
            raise RuntimeError('Snapshot size limit exceeded; use a reviewed streaming solution.')
        name='documents/'+str(doc.pk)
        entry=tarfile.TarInfo(name);entry.size=len(data);entry.mode=0o600
        archive.addfile(entry,io.BytesIO(data))
        manifest.append({'document_id':doc.pk,'storage_key':doc.file.name,'entry':name,'size':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    data=json.dumps({'format':1,'documents':manifest}).encode()
    entry=tarfile.TarInfo('manifest.json');entry.size=len(data);entry.mode=0o600
    archive.addfile(entry,io.BytesIO(data))
'''


def verify(ciphertext, key):
    if len(ciphertext)>MAX_SNAPSHOT_BYTES:
        raise RuntimeError('Snapshot is too large for this small-deployment recovery tool.')
    plain=checked(['openssl','cms','-decrypt','-binary','-inform','DER','-inkey',str(key)],input=ciphertext)
    files={}
    with tarfile.open(fileobj=io.BytesIO(plain),mode='r:gz') as archive:
        total=0
        for member in archive:
            total+=member.size
            if not member.isfile() or total>MAX_SNAPSHOT_BYTES or member.name in files:
                raise RuntimeError('Invalid document archive.')
            if member.name!='manifest.json' and not (member.name.startswith('documents/') and member.name[10:].isdigit()):
                raise RuntimeError('Unexpected archive path.')
            files[member.name]=archive.extractfile(member).read()
    manifest=json.loads(files.pop('manifest.json'))
    expected={item['entry'] for item in manifest['documents']}
    if manifest['format']!=1 or set(files)!=expected or len(expected)!=len(manifest['documents']):
        raise RuntimeError('Manifest does not match the archive.')
    for item in manifest['documents']:
        data=files[item['entry']]
        if len(data)!=item['size'] or hashlib.sha256(data).hexdigest()!=item['sha256']:
            raise RuntimeError('Document integrity check failed.')
    return manifest, files


def restore(ciphertext, key, destination):
    manifest,files=verify(ciphertext,key)  # Verify ALL content before writing anything.
    destination.mkdir(mode=0o700,parents=False,exist_ok=False)
    (destination/'documents').mkdir(mode=0o700)
    for name,data in files.items():
        path=destination/name
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as output: output.write(data)
    fd=os.open(destination/'manifest.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as output:json.dump(manifest,output)
    return len(files)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['capture','verify','restore'])
    parser.add_argument('--host')
    parser.add_argument('--app-dir',default='/home/deploy/apps/django-analytics-dashboard')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--snapshot',type=Path)
    parser.add_argument('--destination',type=Path)
    parser.add_argument('--key-dir',type=Path,default=Path.home()/'.local/share/nuviamy-recovery')
    args=parser.parse_args()
    if args.action=='capture':
        if not args.host or not args.output_dir:parser.error('Capture requires host and output-dir.')
        key,cert=ensure_recipient(args.key_dir)
        remote_cert='/root/.config/nuviamy/recovery-recipient.pem'
        checked(['ssh',args.host,'umask 077; mkdir -p /root/.config/nuviamy; cat > '+remote_cert],input=cert.read_bytes())
        command=shlex.join(['docker','compose','--project-directory',args.app_dir,'exec','-T','web','python','-c',REMOTE_CAPTURE])
        command+=' | '+shlex.join(['openssl','cms','-encrypt','-aes-256-gcm','-binary','-outform','DER','-recip',remote_cert,'-keyopt','rsa_padding_mode:oaep'])
        ciphertext=checked(['ssh',args.host,'bash -o pipefail -c '+shlex.quote(command)])
        manifest,_=verify(ciphertext,key)
        args.output_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
        if args.output_dir.stat().st_mode & 0o077:raise RuntimeError('Output directory must be private (0700).')
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        path=args.output_dir/('nuviamy-documents-'+stamp+'.cms')
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as output: output.write(ciphertext)
        print(json.dumps({'snapshot':str(path),'documents_verified':len(manifest['documents']),'ciphertext_sha256':hashlib.sha256(ciphertext).hexdigest()}))
    else:
        if not args.snapshot:parser.error('Specify snapshot.')
        key=args.key_dir/'recovery-private.pem'
        ciphertext=args.snapshot.read_bytes()
        if args.action=='restore':
            if not args.destination:parser.error('Restore requires a NEW isolated destination.')
            print(json.dumps({'restored_documents':restore(ciphertext,key,args.destination),'production_modified':False}))
        else:
            manifest,_=verify(ciphertext,key)
            print(json.dumps({'documents_verified':len(manifest['documents'])}))


if __name__=='__main__':main()
