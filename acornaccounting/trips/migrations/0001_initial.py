# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'StoreAccount'
        db.create_table('trips_storeaccount', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounts.Account'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=50, blank=True)),
        ))
        db.send_create_signal('trips', ['StoreAccount'])

        # Adding model 'TripEntry'
        db.create_table('trips_tripentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('date', self.gf('django.db.models.fields.DateField')()),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=60)),
            ('number', self.gf('django.db.models.fields.CharField')(max_length=15)),
            ('total_trip_advance', self.gf('django.db.models.fields.DecimalField')(max_digits=19, decimal_places=4)),
            ('amount', self.gf('django.db.models.fields.DecimalField')(max_digits=19, decimal_places=4)),
            ('comments', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('created_at', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now, auto_now_add=True, blank=True)),
        ))
        db.send_create_signal('trips', ['TripEntry'])

        # Adding model 'TripTransaction'
        db.create_table('trips_triptransaction', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('trip_entry', self.gf('django.db.models.fields.related.ForeignKey')(related_name='transaction_set', to=orm['trips.TripEntry'])),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounts.Account'], on_delete=models.PROTECT)),
            ('detail', self.gf('django.db.models.fields.CharField')(max_length=50, blank=True)),
            ('amount', self.gf('django.db.models.fields.DecimalField')(max_digits=19, decimal_places=4)),
        ))
        db.send_create_signal('trips', ['TripTransaction'])

        # Adding model 'TripStoreTransaction'
        db.create_table('trips_tripstoretransaction', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('trip_entry', self.gf('django.db.models.fields.related.ForeignKey')(related_name='store_transaction_set', to=orm['trips.TripEntry'])),
            ('store', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['trips.StoreAccount'], on_delete=models.PROTECT)),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounts.Account'], on_delete=models.PROTECT)),
            ('detail', self.gf('django.db.models.fields.CharField')(max_length=50, blank=True)),
            ('amount', self.gf('django.db.models.fields.DecimalField')(max_digits=19, decimal_places=4)),
        ))
        db.send_create_signal('trips', ['TripStoreTransaction'])

        # Adding model 'TripReceipt'
        db.create_table('trips_tripreceipt', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('trip_entry', self.gf('django.db.models.fields.related.ForeignKey')(related_name='receipt_set', to=orm['trips.TripEntry'])),
            ('receipt_file', self.gf('django.db.models.fields.files.FileField')(max_length=100, null=True, blank=True)),
        ))
        db.send_create_signal('trips', ['TripReceipt'])


    def backwards(self, orm):
        # Deleting model 'StoreAccount'
        db.delete_table('trips_storeaccount')

        # Deleting model 'TripEntry'
        db.delete_table('trips_tripentry')

        # Deleting model 'TripTransaction'
        db.delete_table('trips_triptransaction')

        # Deleting model 'TripStoreTransaction'
        db.delete_table('trips_tripstoretransaction')

        # Deleting model 'TripReceipt'
        db.delete_table('trips_tripreceipt')


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
        'trips.storeaccount': {
            'Meta': {'ordering': "('name',)", 'object_name': 'StoreAccount'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['accounts.Account']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'})
        },
        'trips.tripentry': {
            'Meta': {'ordering': "('date', 'number', 'name')", 'object_name': 'TripEntry'},
            'amount': ('django.db.models.fields.DecimalField', [], {'max_digits': '19', 'decimal_places': '4'}),
            'comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'auto_now_add': 'True', 'blank': 'True'}),
            'date': ('django.db.models.fields.DateField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '60'}),
            'number': ('django.db.models.fields.CharField', [], {'max_length': '15'}),
            'total_trip_advance': ('django.db.models.fields.DecimalField', [], {'max_digits': '19', 'decimal_places': '4'})
        },
        'trips.tripreceipt': {
            'Meta': {'object_name': 'TripReceipt'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'receipt_file': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'trip_entry': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'receipt_set'", 'to': "orm['trips.TripEntry']"})
        },
        'trips.tripstoretransaction': {
            'Meta': {'ordering': "['trip_entry', 'id']", 'object_name': 'TripStoreTransaction'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['accounts.Account']", 'on_delete': 'models.PROTECT'}),
            'amount': ('django.db.models.fields.DecimalField', [], {'max_digits': '19', 'decimal_places': '4'}),
            'detail': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'store': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['trips.StoreAccount']", 'on_delete': 'models.PROTECT'}),
            'trip_entry': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'store_transaction_set'", 'to': "orm['trips.TripEntry']"})
        },
        'trips.triptransaction': {
            'Meta': {'ordering': "['trip_entry', 'id']", 'object_name': 'TripTransaction'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['accounts.Account']", 'on_delete': 'models.PROTECT'}),
            'amount': ('django.db.models.fields.DecimalField', [], {'max_digits': '19', 'decimal_places': '4'}),
            'detail': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'trip_entry': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'transaction_set'", 'to': "orm['trips.TripEntry']"})
        }
    }

    complete_apps = ['trips']