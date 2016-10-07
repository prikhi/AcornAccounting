from django.contrib import admin

from .models import BankAccount, CheckRange


class CheckRangeInline(admin.TabularInline):
    model = CheckRange


class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('account', 'bank')
    fields = ('account', 'bank')
    inlines = (CheckRangeInline,)

admin.site.register(BankAccount, BankAccountAdmin)
