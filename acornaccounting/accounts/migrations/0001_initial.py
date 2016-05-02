# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Header'
        db.create_table('accounts_header', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=50)),
            ('type', self.gf('django.db.models.fields.PositiveSmallIntegerField')(blank=True)),
            ('description', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('slug', self.gf('django.db.models.fields.SlugField')(unique=True, max_length=50)),
            ('full_number', self.gf('django.db.models.fields.CharField')(max_length=7, null=True, blank=True)),
            (u'lft', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            (u'rght', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            (u'tree_id', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            (u'level', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('parent', self.gf('mptt.fields.TreeForeignKey')(to=orm['accounts.Header'], null=True, blank=True)),
            ('active', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal('accounts', ['Header'])

        # Adding model 'Account'
        db.create_table('accounts_account', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=50)),
            ('type', self.gf('django.db.models.fields.PositiveSmallIntegerField')(blank=True)),
            ('description', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('slug', self.gf('django.db.models.fields.SlugField')(unique=True, max_length=50)),
            ('full_number', self.gf('django.db.models.fields.CharField')(max_length=7, null=True, blank=True)),
            (u'lft', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            (u'rght', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            (u'tree_id', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            (u'level', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('balance', self.gf('django.db.models.fields.DecimalField')(default='0.00', max_digits=19, decimal_places=4)),
            ('reconciled_balance', self.gf('django.db.models.fields.DecimalField')(default='0.00', max_digits=19, decimal_places=4)),
            ('parent', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounts.Header'])),
            ('active', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('bank', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('last_reconciled', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
        ))
        db.send_create_signal('accounts', ['Account'])

        # Adding model 'HistoricalAccount'
        db.create_table('accounts_historicalaccount', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounts.Account'], null=True, on_delete=models.SET_NULL, blank=True)),
            ('number', self.gf('django.db.models.fields.CharField')(max_length=7)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('type', self.gf('django.db.models.fields.PositiveSmallIntegerField')()),
            ('amount', self.gf('django.db.models.fields.DecimalField')(max_digits=19, decimal_places=4)),
            ('date', self.gf('django.db.models.fields.DateField')()),
        ))
        db.send_create_signal('accounts', ['HistoricalAccount'])

        # Adding unique constraint on 'HistoricalAccount', fields ['date', 'name']
        db.create_unique('accounts_historicalaccount', ['date', 'name'])


    def backwards(self, orm):
        # Removing unique constraint on 'HistoricalAccount', fields ['date', 'name']
        db.delete_unique('accounts_historicalaccount', ['date', 'name'])

        # Deleting model 'Header'
        db.delete_table('accounts_header')

        # Deleting model 'Account'
        db.delete_table('accounts_account')

        # Deleting model 'HistoricalAccount'
        db.delete_table('accounts_historicalaccount')


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
        'accounts.historicalaccount': {
            'Meta': {'ordering': "['date', 'number']", 'unique_together': "(('date', 'name'),)", 'object_name': 'HistoricalAccount'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['accounts.Account']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'amount': ('django.db.models.fields.DecimalField', [], {'max_digits': '19', 'decimal_places': '4'}),
            'date': ('django.db.models.fields.DateField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'number': ('django.db.models.fields.CharField', [], {'max_length': '7'}),
            'type': ('django.db.models.fields.PositiveSmallIntegerField', [], {})
        }
    }

    complete_apps = ['accounts']