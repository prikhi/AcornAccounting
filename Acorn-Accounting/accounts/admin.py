from django.contrib import admin
from mptt.admin import MPTTModelAdmin

from .models import Header, Account


class AccountAdmin(admin.ModelAdmin):
    list_display = ('get_full_number', 'name', 'parent', 'description',
                    'balance',)
    list_display_links = ('name', 'get_full_number')
    list_per_page = 50
    ordering = ('parent__lft', 'name')
    search_field = ['name', 'description', 'type']
    prepopulated_fields = {'slug': ('name',)}
    exclude = ('type',)

admin.site.register(Account, AccountAdmin)


class HeaderAdmin(MPTTModelAdmin):
    list_display = ('get_full_number', 'name', 'description', 'type')
    list_display_links = ('get_full_number', 'name')
    list_per_page = 50
    search_field = ['name', 'description', 'type']
    prepopulated_fields = {'slug': ('name',)}

admin.site.register(Header, HeaderAdmin)
