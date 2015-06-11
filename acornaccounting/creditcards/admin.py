from django.contrib import admin

from .models import CreditCard


class CreditCardAdmin(admin.ModelAdmin):
    list_display = ('name', 'account')

admin.site.register(CreditCard, CreditCardAdmin)
