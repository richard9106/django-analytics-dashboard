import json
from html.parser import HTMLParser
from django.test import SimpleTestCase, RequestFactory, override_settings
from django.urls import reverse
from django.http import HttpResponse
from .marketing import PublicWebsiteCanonicalMiddleware


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}; self.canonicals = []; self.h1_count = 0
        self.in_schema = False; self.schema_text = ''; self.schemas = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            self.meta[attrs.get('name', attrs.get('property'))] = attrs.get('content')
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonicals.append(attrs['href'])
        if tag == 'h1': self.h1_count += 1
        if tag == 'script' and attrs.get('type') == 'application/ld+json':
            self.in_schema = True; self.schema_text = ''

    def handle_data(self, data):
        if self.in_schema: self.schema_text += data

    def handle_endtag(self, tag):
        if tag == 'script' and self.in_schema:
            self.schemas.append(json.loads(self.schema_text)); self.in_schema = False


class MarketingSEOTests(SimpleTestCase):
    def test_public_pages_have_consistent_metadata_and_one_heading(self):
        for name in ('home', 'features', 'pricing', 'therapy_practice_management',
                     'therapy_scheduling_software', 'clinical_notes_software',
                     'client_portal_software', 'mental_health_billing_software',
                     'help_center', 'support_contact', 'privacy_policy',
                     'cookie_policy', 'terms_of_service', 'legal_notice'):
            with self.subTest(page=name):
                path = reverse(name)
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                parser = MetadataParser(); parser.feed(response.content.decode())
                self.assertEqual(parser.canonicals, ['https://nuviamy.com' + path])
                self.assertEqual(parser.h1_count, 1)
                self.assertTrue(parser.meta['description'])
                self.assertEqual(parser.meta['og:url'], parser.canonicals[0])
                self.assertTrue(parser.meta['og:image'].startswith('https://nuviamy.com/static/marketing/nuviamy-social'))
                self.assertEqual(parser.meta['twitter:image'], parser.meta['og:image'])
                self.assertNotIn('keywords', parser.meta)

    def test_home_offer_is_priced_and_demo_images_identified(self):
        response = self.client.get(reverse('home'))
        parser = MetadataParser(); parser.feed(response.content.decode())
        offer = parser.schemas[0]['offers']
        self.assertEqual((offer['price'], offer['priceCurrency']), ('39', 'USD'))
        self.assertContains(response, 'Fictional demonstration data')
        self.assertNotContains(response, 'keyword-cloud')
        self.assertNotContains(response, 'aggregateRating')

    def test_search_variants_are_not_indexed(self):
        for path in (reverse('help_center') + '?q=calendar', reverse('support_contact') + '?sent=1'):
            parser = MetadataParser(); parser.feed(self.client.get(path).content.decode())
            self.assertEqual(parser.meta['robots'], 'noindex,follow')

    @override_settings(ALLOWED_HOSTS=['www.nuviamy.com', 'localhost'])
    def test_www_redirect_preserves_query_and_does_not_intercept_app_or_posts(self):
        middleware = PublicWebsiteCanonicalMiddleware(lambda request: HttpResponse('unchanged'))
        factory = RequestFactory()
        response = middleware(factory.get('/help/?q=calendar', HTTP_HOST='www.nuviamy.com'))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], 'https://nuviamy.com/help/?q=calendar')
        for request in (factory.post('/help/contact/', HTTP_HOST='www.nuviamy.com'),
                        factory.get('/clients/', HTTP_HOST='www.nuviamy.com'),
                        factory.get('/', HTTP_HOST='localhost')):
            self.assertEqual(middleware(request).content, b'unchanged')
