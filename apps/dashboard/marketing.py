"""Canonical host handling for public website pages only."""
from django.http import HttpResponsePermanentRedirect

PUBLIC_WEBSITE_PATHS = frozenset({
    '/', '/features/', '/pricing/', '/help/', '/help/contact/', '/privacy/',
    '/cookie-policy/', '/terms/', '/legal/', '/therapy-practice-management-software/',
    '/therapy-scheduling-software/', '/clinical-notes-software-for-therapists/',
    '/client-portal-software-for-therapists/', '/mental-health-billing-software/',
    '/robots.txt', '/sitemap.xml',
})


class PublicWebsiteCanonicalMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (request.method in {'GET', 'HEAD'}
                and request.get_host().split(':')[0].lower() == 'www.nuviamy.com'
                and request.path in PUBLIC_WEBSITE_PATHS):
            return HttpResponsePermanentRedirect('https://nuviamy.com' + request.get_full_path())
        return self.get_response(request)
