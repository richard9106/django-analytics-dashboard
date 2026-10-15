from io import BytesIO
import zipfile
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image
from .uploads import MAX_DOCUMENT_BYTES, validate_document_upload


class DocumentUploadValidationTests(SimpleTestCase):
    def test_client_supplied_mime_does_not_determine_type(self):
        f=SimpleUploadedFile('note.pdf', b'%PDF-1.7\nsynthetic', content_type='text/html')
        self.assertEqual(validate_document_upload(f),'application/pdf')
        self.assertEqual(f.tell(),0)

    def test_executable_and_renamed_executable_are_rejected(self):
        for name,data in [('file.exe',b'MZ'),('file.pdf',b'MZ'),('file.png',b'MZ'),('file.docx',b'MZ')]:
            with self.subTest(name=name), self.assertRaises(ValidationError):
                validate_document_upload(SimpleUploadedFile(name,data))

    def test_empty_oversized_and_binary_text_are_rejected(self):
        for data in (b'',b'x'*(MAX_DOCUMENT_BYTES+1),b'\x00\xff'):
            with self.assertRaises(ValidationError):
                validate_document_upload(SimpleUploadedFile('note.txt',data))

    def test_valid_image_is_verified(self):
        data=BytesIO();Image.new('RGB',(2,2)).save(data,format='PNG')
        self.assertEqual(validate_document_upload(SimpleUploadedFile('image.png',data.getvalue())),'image/png')

    def test_docx_container_with_macros_is_rejected(self):
        data=BytesIO()
        with zipfile.ZipFile(data,'w') as archive:
            archive.writestr('[Content_Types].xml','<Types/>')
            archive.writestr('word/document.xml','<document/>')
            archive.writestr('word/vbaProject.bin',b'synthetic')
        with self.assertRaises(ValidationError):
            validate_document_upload(SimpleUploadedFile('note.docx',data.getvalue()))
