# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'CreditCard'
        db.create_table('creditcards_creditcard', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounts.Account'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=50, blank=True)),
        ))
        db.send_create_signal('creditcards', ['CreditCard'])

        # Adding model 'CreditCardEntry'
        db.create_table('creditcards_creditcardentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('date', self.gf('django.db.models.fields.DateField')()),
            ('card', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['creditcards.CreditCard'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=60)),
            ('merchant', self.gf('django.db.models.fields.CharField')(max_length=60)),
            ('amount', self.gf('django.db.models.fields.DecimalField')(max_digits=19, decimal_places=4)),
            ('comments', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('created_at', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now, auto_now_add=True, blank=True)),
        ))
        db.send_create_signal('creditcards', ['CreditCardEntry'])

        # Adding model 'CreditCardTransaction'
        db.create_table('creditcards_creditcardtransaction', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('creditcard_entry', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['creditcards.CreditCardEntry'])),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounts.Account'], on_delete=models.PROTECT)),
            ('detail', self.gf('django.db.models.fields.CharField')(max_length=50, blank=True)),
            ('amount', self.gf('django.db.models.fields.DecimalField')(max_digits=19, decimal_places=4)),
        ))
        db.send_create_signal('creditcards', ['CreditCardTransaction'])


    def backwards(self, orm):
        # Deleting model 'CreditCard'
        db.delete_table('creditcards_creditcard')

        # Deleting model 'CreditCardEntry'
        db.delete_table('creditcards_creditcardentry')

        # Deleting model 'CreditCardTransaction'
        db.delete_table('creditcards_creditcardtransaction')


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
        'creditcards.creditcard': {
            'Meta': {'ordering': "('name',)", 'object_name': 'CreditCard'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['accounts.Account']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'})
        },
        'creditcards.creditcardentry': {
            'Meta': {'ordering': "('created_at',)", 'object_name': 'CreditCardEntry'},
            'amount': ('django.db.models.fields.DecimalField', [], {'max_digits': '19', 'decimal_places': '4'}),
            'card': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['creditcards.CreditCard']"}),
            'comments': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'auto_now_add': 'True', 'blank': 'True'}),
            'date': ('django.db.models.fields.DateField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'merchant': ('django.db.models.fields.CharField', [], {'max_length': '60'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '60'})
        },
        'creditcards.creditcardtransaction': {
            'Meta': {'ordering': "['id']", 'object_name': 'CreditCardTransaction'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['accounts.Account']", 'on_delete': 'models.PROTECT'}),
            'amount': ('django.db.models.fields.DecimalField', [], {'max_digits': '19', 'decimal_places': '4'}),
            'creditcard_entry': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['creditcards.CreditCardEntry']"}),
            'detail': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        }
    }

    complete_apps = ['creditcards']