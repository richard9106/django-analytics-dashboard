import copy
import json
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from apps.accounts.models import UserProfile
from apps.clients.models import Client
from apps.practices.models import Practice
from .models import IntakePacketTemplate, ClientIntakeAssignment, ClientPortalAccess
from .forms import IntakePacketTemplateForm, ClientIntakeResponseForm
from .intake_schema import flatten_schema


def schema():
    return {'version': 1, 'pages': [
        {'id': 'page1', 'title': 'About you', 'description': 'Tell us a little about yourself.', 'questions': [
            {'id': 'name', 'label': 'Preferred name', 'type': 'short_text', 'required': True},
            {'id': 'goals', 'label': 'Your goals', 'type': 'long_text', 'required': False},
            {'id': 'contact', 'label': 'Contact preference', 'type': 'single_choice', 'required': True, 'options': ['Email', 'Phone']}]},
        {'id': 'page2', 'title': 'Preferences', 'questions': [
            {'id': 'topics', 'label': 'Topics', 'type': 'multiple_choice', 'required': True, 'options': ['Work', 'Family']},
            {'id': 'time', 'label': 'Time', 'type': 'dropdown', 'required': False, 'options': ['Morning', 'Afternoon']},
            {'id': 'previous', 'label': 'Previous sessions?', 'type': 'yes_no', 'required': True}]}]}


@override_settings(MFA_REQUIRED=False, EMAIL_TWO_STEP_REQUIRED=False)
class IntakeBuilderTests(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(name='Builder demo')
        self.owner = get_user_model().objects.create_user('builder-owner')
        UserProfile.objects.create(user=self.owner, practice=self.practice, role='owner')
        self.patient = Client.objects.create(practice=self.practice, first_name='Demo', last_name='Client')

    def template(self):
        form = IntakePacketTemplateForm({'name': 'Welcome', 'active': 'on', 'form_structure': json.dumps(schema())}, practice=self.practice)
        self.assertTrue(form.is_valid(), form.errors)
        return form.save()

    def test_pages_types_and_options_round_trip_and_snapshot_remains_frozen(self):
        template = self.template()
        self.assertEqual(len(template.questions), 6)
        assignment = ClientIntakeAssignment.objects.create(practice=self.practice, client=self.patient, template=template)
        original = copy.deepcopy(assignment.packet_questions)
        changed = schema(); changed['pages'].reverse(); changed['pages'][0]['title'] = 'Changed'
        form = IntakePacketTemplateForm({'name': 'Welcome', 'form_structure': json.dumps(changed)}, instance=template, practice=self.practice)
        self.assertTrue(form.is_valid(), form.errors); form.save()
        assignment.refresh_from_db()
        self.assertEqual(assignment.packet_questions, original)
        initial = json.loads(IntakePacketTemplateForm(instance=template, practice=self.practice)['form_structure'].value())
        self.assertEqual(initial['pages'][0]['title'], 'Changed')

    def test_server_rejects_invalid_schema_instead_of_falling_back_to_plain_text(self):
        for mutation in ['unknown_type', 'duplicate_id', 'empty_page', 'duplicate_options', 'not_bool', 'long_label']:
            data = schema()
            if mutation == 'unknown_type': data['pages'][0]['questions'][0]['type'] = 'html'
            if mutation == 'duplicate_id': data['pages'][1]['questions'][0]['id'] = 'name'
            if mutation == 'empty_page': data['pages'][0]['questions'] = []
            if mutation == 'duplicate_options': data['pages'][0]['questions'][2]['options'] = ['Same', 'Same']
            if mutation == 'not_bool': data['pages'][0]['questions'][0]['required'] = 'false'
            if mutation == 'long_label': data['pages'][0]['questions'][0]['label'] = 'X' * 501
            with self.subTest(mutation=mutation):
                form = IntakePacketTemplateForm({'name': 'Bad', 'form_structure': json.dumps(data), 'question_lines': 'Fallback?'}, practice=self.practice)
                self.assertFalse(form.is_valid()); self.assertIn('form_structure', form.errors)
        self.assertFalse(IntakePacketTemplate.objects.exists())

    def test_limits_and_malformed_payloads(self):
        for value in ['{', '[]', '{"version":2,"pages":[]}', 'null']:
            form = IntakePacketTemplateForm({'name': 'Bad', 'form_structure': value}, practice=self.practice)
            self.assertFalse(form.is_valid())
        data = schema(); data['pages'] *= 11
        with self.assertRaises(ValidationError): flatten_schema(data)
        data = schema(); question = data['pages'][0]['questions'][0]
        data['pages'] = [{'id':'large', 'title':'Large page', 'questions':[{**question,'id':f'q{i}'} for i in range(101)]}]
        with self.assertRaises(ValidationError): flatten_schema(data)

    def test_typed_answers_validate_choices_required_and_optional_fields(self):
        assignment = ClientIntakeAssignment.objects.create(practice=self.practice, client=self.patient, template=self.template())
        bad = ClientIntakeResponseForm({'question_0': 'Alex', 'question_2': 'Not an option', 'question_3': ['Work','Hacked'], 'question_5': 'Yes'}, assignment=assignment)
        self.assertFalse(bad.is_valid()); self.assertIn('question_2', bad.errors); self.assertIn('question_3', bad.errors)
        blank = ClientIntakeResponseForm({}, assignment=assignment)
        self.assertFalse(blank.is_valid()); self.assertIn('question_3', blank.errors)
        good = ClientIntakeResponseForm({'question_0': 'Alex', 'question_2': 'Email', 'question_3': ['Work','Family'], 'question_5': 'No'}, assignment=assignment)
        self.assertTrue(good.is_valid(), good.errors)
        self.assertEqual([p['title'] for p in good.pages], ['About you','Preferences'])
        good.save(); assignment.refresh_from_db()
        self.assertEqual(assignment.answers['question_3']['answer'], ['Work','Family'])
        self.assertEqual(assignment.response_items[3]['answer'], 'Work\nFamily')
        self.assertEqual(assignment.answers['question_1']['answer'], '')

    def test_portal_renders_pages_escapes_text_and_rejects_foreign_assignment(self):
        template = self.template(); template.questions[0]['label'] = '<script>alert(1)</script>'; template.save()
        assignment = ClientIntakeAssignment.objects.create(practice=self.practice, client=self.patient, template=template)
        user = get_user_model().objects.create_user('builder-patient')
        ClientPortalAccess.objects.create(user=user, practice=self.practice, client=self.patient)
        self.client.force_login(user)
        response = self.client.get(reverse('portal:intake_complete', args=[assignment.pk]))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'data-intake-page',count=3)  # form marker plus two pages
        self.assertContains(response,'&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response,'<script>alert(1)</script>')
        response = self.client.post(reverse('portal:intake_complete', args=[assignment.pk]),
            {'question_0':'Demo', 'question_2':'Email', 'question_3':['Work','Family'], 'question_5':'No'})
        self.assertEqual(response.status_code,302)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, ClientIntakeAssignment.Status.SUBMITTED)
        self.assertEqual(assignment.answers['question_3']['answer'], ['Work','Family'])
        other = Client.objects.create(practice=self.practice,first_name='Other',last_name='Client')
        foreign = ClientIntakeAssignment.objects.create(practice=self.practice,client=other,template=template)
        self.assertEqual(self.client.get(reverse('portal:intake_complete',args=[foreign.pk])).status_code,404)

    def test_new_editor_get_and_create_preserve_permissions(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse('intake:template_create')),'data-intake-builder')
        response = self.client.post(reverse('intake:template_create'),{'name':'Welcome','active':'on','form_structure':json.dumps(schema())})
        self.assertEqual(response.status_code,302)
        self.assertEqual(IntakePacketTemplate.objects.get().questions[3]['type'],'multiple_choice')
