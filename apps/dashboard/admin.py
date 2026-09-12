from django.contrib import admin

from .models import Customer, OperationalEvent, Product, Sale

admin.site.register([Customer, Product, Sale, OperationalEvent])
