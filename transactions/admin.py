from django.contrib import admin
from .models import Transaction, BehaviorBaseline, LedgerEntry

admin.site.register(Transaction)
admin.site.register(BehaviorBaseline)
admin.site.register(LedgerEntry)
