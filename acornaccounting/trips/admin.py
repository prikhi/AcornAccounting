from django.contrib import admin

from .models import StoreAccount


class StoreAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'account')

admin.site.register(StoreAccount, StoreAccountAdmin)
