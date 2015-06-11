# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Receipt'
        db.create_table('receipts_receipt', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('journal_entry', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['entries.JournalEntry'], unique=True)),
            ('receipt_file', self.gf('django.db.models.fields.files.FileField')(max_length=100)),
        ))
        db.send_create_signal('receipts', ['Receipt'])


    def backwards(self, orm):
        # Deleting model 'Receipt'
        db.delete_table('receipts_receipt')


    models = {
        'entries.journalentry': {
            'Meta': {'ordering': "['date', 'id']", 'object_name': 'JournalEntry'},
            'comments': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'auto_now_add': 'True', 'blank': 'True'}),
            'date': ('django.db.models.fields.DateField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'memo': ('django.db.models.fields.CharField', [], {'max_length': '60'}),
            'updated_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'auto_now': 'True', 'blank': 'True'})
        },
        'receipts.receipt': {
            'Meta': {'object_name': 'Receipt'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'journal_entry': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['entries.JournalEntry']", 'unique': 'True'}),
            'receipt_file': ('django.db.models.fields.files.FileField', [], {'max_length': '100'})
        }
    }

    complete_apps = ['receipts']