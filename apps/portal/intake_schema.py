"""Versioned form-builder questions, retaining the existing assignment snapshot format."""
import re
from uuid import uuid4
from django.core.exceptions import ValidationError

TYPES = {'short_text', 'long_text', 'single_choice', 'multiple_choice', 'dropdown', 'yes_no'}
CHOICES = {'single_choice', 'multiple_choice', 'dropdown'}


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', value):
        raise ValidationError('Page and question identifiers are invalid. Reload the editor and try again.')
    return value


def text(value, label, limit, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValidationError(f'{label} must contain {"1–" if required else "at most "}{limit} characters.')
    return value.strip()


def flatten_schema(schema):
    if not isinstance(schema, dict) or schema.get('version') != 1:
        raise ValidationError('Unsupported form format.')
    pages = schema.get('pages')
    if not isinstance(pages, list) or not 1 <= len(pages) <= 20:
        raise ValidationError('Add between 1 and 20 pages.')
    records, page_ids, question_ids = [], set(), set()
    for page in pages:
        if not isinstance(page, dict):
            raise ValidationError('Invalid page.')
        pid = identifier(page.get('id'))
        if pid in page_ids:
            raise ValidationError('Each page needs a unique identifier.')
        page_ids.add(pid)
        title = text(page.get('title'), 'Page title', 160, True)
        description = text(page.get('description', ''), 'Page instructions', 2000)
        questions = page.get('questions')
        if not isinstance(questions, list) or not questions:
            raise ValidationError('Each page needs at least one question.')
        for question in questions:
            if not isinstance(question, dict):
                raise ValidationError('Invalid question.')
            qid = identifier(question.get('id'))
            if qid in question_ids:
                raise ValidationError('Each question needs a unique identifier.')
            question_ids.add(qid)
            kind = question.get('type')
            if kind not in TYPES:
                raise ValidationError('Choose a supported question type.')
            if type(question.get('required')) is not bool:
                raise ValidationError('Specify whether each question is required.')
            label = text(question.get('label'), 'Question title', 500, True)
            help_text = text(question.get('help_text', ''), 'Question help', 2000)
            options = []
            if kind in CHOICES:
                options = question.get('options')
                if not isinstance(options, list) or not 2 <= len(options) <= 50:
                    raise ValidationError('Selection questions need between 2 and 50 options.')
                options = [text(option, 'Option', 200, True) for option in options]
                if len(set(options)) != len(options):
                    raise ValidationError('Options must be different.')
            records.append({'_builder_version': 1, 'id': qid, 'label': label, 'type': kind,
                            'required': question['required'], 'help_text': help_text, 'options': options,
                            'page_id': pid, 'page_title': title, 'page_description': description})
            if len(records) > 100:
                raise ValidationError('A form can contain at most 100 questions.')
    return records


def pages_from_questions(questions):
    pages = []
    for index, original in enumerate(questions):
        q = dict(original) if isinstance(original, dict) else {'label': str(original)}
        authored = q.get('_builder_version') == 1
        pid = q.get('page_id') if authored else 'legacy-page'
        if not pages or pages[-1]['id'] != pid:
            pages.append({'id': pid, 'title': q.get('page_title', 'Your information') if authored else 'Your information',
                          'description': q.get('page_description', '') if authored else '', 'questions': []})
        pages[-1]['questions'].append({
            'id': q.get('id') if authored else f'legacy-question-{index}',
            'label': str(q.get('label') or q.get('question') or q.get('id') or 'Question'),
            'type': q.get('type') if authored else 'long_text',
            'required': q.get('required', True) if authored else True,
            'help_text': q.get('help_text', '') if authored else '',
            'options': q.get('options', []) if authored else [], 'index': index,
        })
    if not pages:
        pages = [{'id': 'page-' + uuid4().hex, 'title': 'Your information', 'description': '', 'questions': []}]
    return pages
