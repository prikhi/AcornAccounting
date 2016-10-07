# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'CheckRange'
        db.create_table('bank_import_checkrange', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('bank_account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['bank_import.BankAccount'])),
            ('start_number', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('end_number', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('default_account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounts.Account'])),
            ('default_payee', self.gf('django.db.models.fields.CharField')(max_length=50, blank=True)),
            ('default_memo', self.gf('django.db.models.fields.CharField')(max_length=60, blank=True)),
        ))
        db.send_create_signal('bank_import', ['CheckRange'])


    def backwards(self, orm):
        # Deleting model 'CheckRange'
        db.delete_table('bank_import_checkrange')


    models = {
        'accounts.account': {
            'Meta': {'ordering': "['name']", 'object_name': 'Account'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'balance': ('django.db.models.fields.DecimalField', [], {'default': "'0.00'", 'max_digits': '19', 'decimal_places': '4'}),
            'bank': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'full_number': ('django.db.models.fields.CharField', [], {'max_length': '7', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_reconciled': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            u'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            u'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '50'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['accounts.Header']"}),
            'reconciled_balance': ('django.db.models.fields.DecimalField', [], {'default': "'0.00'", 'max_digits': '19', 'decimal_places': '4'}),
            u'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '50'}),
            u'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'type': ('django.db.models.fields.PositiveSmallIntegerField', [], {'blank': 'True'})
        },
        'accounts.header': {
            'Meta': {'ordering': "['name']", 'object_name': 'Header'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'full_number': ('django.db.models.fields.CharField', [], {'max_length': '7', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            u'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            u'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '50'}),
            'parent': ('mptt.fields.TreeForeignKey', [], {'to': "orm['accounts.Header']", 'null': 'True', 'blank': 'True'}),
            u'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '50'}),
            u'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'type': ('django.db.models.fields.PositiveSmallIntegerField', [], {'blank': 'True'})
        },
        'bank_import.bankaccount': {
            'Meta': {'ordering': "('name',)", 'object_name': 'BankAccount'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['accounts.Account']"}),
            'bank': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'})
        },
        'bank_import.checkrange': {
            'Meta': {'object_name': 'CheckRange'},
            'bank_account': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['bank_import.BankAccount']"}),
            'default_account': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['accounts.Account']"}),
            'default_memo': ('django.db.models.fields.CharField', [], {'max_length': '60', 'blank': 'True'}),
            'default_payee': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'end_number': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'start_number': ('django.db.models.fields.PositiveIntegerField', [], {})
        }
    }

    complete_apps = ['bank_import']