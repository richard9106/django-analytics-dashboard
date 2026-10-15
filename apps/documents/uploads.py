"""Bound upload size and validate supported containers; this is not a malware scanner."""
from io import BytesIO
from pathlib import PurePath
import zipfile
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


def validate_document_upload(upload):
    if not upload.size or upload.size > MAX_DOCUMENT_BYTES:
        raise ValidationError('Upload a non-empty document up to 10 MB.')
    suffix = PurePath(upload.name).suffix.lower()
    if suffix not in {'.pdf', '.txt', '.png', '.jpg', '.jpeg', '.docx'}:
        raise ValidationError('Use a PDF, DOCX, PNG, JPEG or UTF-8 text document.')
    position = upload.tell()
    try:
        upload.seek(0)
        data = upload.read(MAX_DOCUMENT_BYTES + 1)
        if len(data) > MAX_DOCUMENT_BYTES:
            raise ValidationError('Documents must be 10 MB or smaller.')
        if suffix == '.pdf':
            if not data.startswith(b'%PDF-'):
                raise ValidationError('The file does not contain a PDF document.')
            return 'application/pdf'
        if suffix == '.txt':
            if b'\x00' in data:
                raise ValidationError('Text documents must contain UTF-8 text.')
            try:
                data.decode('utf-8')
            except UnicodeDecodeError:
                raise ValidationError('Text documents must contain UTF-8 text.')
            return 'text/plain'
        if suffix == '.docx':
            try:
                with zipfile.ZipFile(BytesIO(data)) as archive:
                    infos = archive.infolist()
                    names = {i.filename for i in infos}
                    if not {'[Content_Types].xml', 'word/document.xml'} <= names:
                        raise ValidationError('The file does not contain a DOCX document.')
                    if len(infos) > 1000 or sum(i.file_size for i in infos) > 25 * 1024 * 1024:
                        raise ValidationError('The DOCX document expands beyond the supported size.')
                    if any(i.flag_bits & 1 or '..' in PurePath(i.filename).parts
                           or i.filename.startswith('/') or any(x in i.filename.lower() for x in ('vbaproject', 'activex/', 'embeddings/')) for i in infos):
                        raise ValidationError('Encrypted DOCX files and embedded active content are not supported.')
            except zipfile.BadZipFile:
                raise ValidationError('The file does not contain a DOCX document.')
            return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        try:
            with Image.open(BytesIO(data)) as image:
                expected = 'PNG' if suffix == '.png' else 'JPEG'
                if image.format != expected or image.width * image.height > 20_000_000:
                    raise ValidationError('Use a valid PNG or JPEG image up to 20 megapixels.')
                image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise ValidationError('Use a valid PNG or JPEG image.')
        return 'image/png' if suffix == '.png' else 'image/jpeg'
    finally:
        upload.seek(position)
