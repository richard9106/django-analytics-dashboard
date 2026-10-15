import json
from django.test import SimpleTestCase
from config.sentry_privacy import before_send, discard_breadcrumb, discard_transaction


class SentryPrivacyTests(SimpleTestCase):
    def test_patient_text_credentials_and_context_are_not_transmitted(self):
        marker='SENSITIVE-PATIENT-PASSWORD-TOKEN'
        event={'event_id':'synthetic-id','level':'error','request':{'data':marker,'url':marker,'headers':{'Authorization':marker}},'user':{'email':marker},'breadcrumbs':{'values':[{'message':marker}]},'extra':{'password':marker},'contexts':{'custom':marker},'transaction':marker,'logentry':{'formatted':marker},'tags':{'patient':marker},'exception':{'values':[{'type':'ValueError','value':marker,'stacktrace':{'frames':[{'filename':'/app/apps/clinical/views.py','function':'form_valid','lineno':42,'vars':{'note':marker},'context_line':marker,'abs_path':marker}]}}]}}
        result=before_send(event,{})
        self.assertNotIn(marker,json.dumps(result))
        frame=result['exception']['values'][0]['stacktrace']['frames'][0]
        self.assertEqual(frame,{'filename':'views.py','function':'form_valid','lineno':42})
        self.assertEqual(result['exception']['values'][0]['type'],'ValueError')

    def test_message_only_errors_breadcrumbs_and_traces_are_dropped(self):
        self.assertIsNone(before_send({'message':'patient text'},{}))
        self.assertIsNone(discard_transaction({'name':'patient text'},{}))
        self.assertIsNone(discard_breadcrumb({'message':'patient text'},{}))
