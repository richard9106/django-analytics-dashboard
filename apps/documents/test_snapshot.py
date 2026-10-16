from io import BytesIO
import hashlib
import json
from pathlib import Path
import tarfile
from tempfile import TemporaryDirectory
from django.test import SimpleTestCase
from ops.document_snapshot import verify, restore
from ops.offsite_config_backup import checked, ensure_recipient
from ops.prepare_migration import prepare, REQUIRED


class DocumentRecoveryTests(SimpleTestCase):
    def snapshot(self,cert,entry='documents/1',data=b'Fictional signed consent v1'):
        plain=BytesIO()
        with tarfile.open(fileobj=plain,mode='w:gz') as archive:
            for name,content in [(entry,data),('manifest.json',json.dumps({'format':1,'documents':[{'entry':entry,'size':len(data),'sha256':hashlib.sha256(data).hexdigest()}]}).encode())]:
                member=tarfile.TarInfo(name);member.size=len(content)
                archive.addfile(member,BytesIO(content))
        return checked(['openssl','cms','-encrypt','-aes-256-gcm','-binary','-outform','DER','-recip',str(cert),'-keyopt','rsa_padding_mode:oaep'],input=plain.getvalue())

    def test_deleted_or_corrupted_working_file_recovers_from_prior_snapshot(self):
        with TemporaryDirectory() as d:
            root=Path(d);key,cert=ensure_recipient(root/'keys')
            ciphertext=self.snapshot(cert)
            work=root/'working.txt';work.write_bytes(b'Fictional signed consent v1')
            work.unlink()
            self.assertEqual(restore(ciphertext,key,root/'restore-deleted'),1)
            expected=(root/'restore-deleted/documents/1').read_bytes()
            work.write_bytes(b'corrupted later version')
            self.assertEqual(restore(ciphertext,key,root/'restore-corrupt'),1)
            self.assertEqual(expected,(root/'restore-corrupt/documents/1').read_bytes())
            self.assertNotEqual(expected,work.read_bytes())
            with self.assertRaises(FileExistsError): restore(ciphertext,key,root/'restore-corrupt')
            altered=ciphertext[:-1]+bytes([ciphertext[-1]^1])
            with self.assertRaises(RuntimeError):restore(altered,key,root/'tampered')
            self.assertFalse((root/'tampered').exists())

    def test_path_traversal_in_encrypted_archive_is_rejected(self):
        with TemporaryDirectory() as d:
            root=Path(d);key,cert=ensure_recipient(root/'keys')
            with self.assertRaises(RuntimeError): verify(self.snapshot(cert,entry='../escape'),key)

    def test_migration_rehearsal_disables_external_actions_and_preserves_key(self):
        from dotenv import dotenv_values
        with TemporaryDirectory() as d:
            root=Path(d);source=root/'source.env'
            values={k:'synthetic-'+k for k in REQUIRED}
            values.update(STRIPE_SECRET_KEY='synthetic-paid-key',EMAIL_BACKEND='smtp',AWS_ACCESS_KEY_ID='synthetic-storage')
            source.write_text(''.join(k+'='+v+'\n' for k,v in values.items()))
            prepare(source,root/'plan','a'*40)
            rehearsal=dotenv_values(root/'plan/rehearsal.env')
            self.assertEqual(rehearsal['STRIPE_SECRET_KEY'],'')
            self.assertEqual(rehearsal['AWS_ACCESS_KEY_ID'],'')
            self.assertEqual(rehearsal['FIELD_ENCRYPTION_KEY'],values['FIELD_ENCRYPTION_KEY'])
            self.assertEqual((root/'plan/production-candidate.env').read_bytes(),source.read_bytes())
            self.assertEqual((root/'plan/rehearsal.env').stat().st_mode&0o777,0o600)
