from django.contrib import admin

from .models import Event


class EventAdmin(admin.ModelAdmin):
    list_display = ('date', 'id', 'name', 'city', 'state')
    search_fields = ['date', 'name']
    list_filter = ['date', 'state']
    list_per_page = 50

admin.site.register(Event, EventAdmin)
