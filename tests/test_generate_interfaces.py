from django.db import models
from django.test import TestCase

from rest_framework import serializers


class CommandTests(TestCase):
    def setUp(self):

        class MyModel(models.Model):
            charfield = models.CharField(max_length=200)

        class MySerializer(serializers.ModelSerializer):
            class Meta:
                model = MyModel

        self.MySerializer = MySerializer

    def test_true(self):
        serializer = self.MySerializer()
        interface = ['interface %s {' % type(serializer).__name__]

        interface_field_mapping = {
            serializers.IntegerField: 'number',
            serializers.CharField: 'string',
        }
        for name, field in self.MySerializer().fields.items():
            mapping = interface_field_mapping.get(type(field), 'any')
            interface.append('    %s = %s;' % (name, mapping))
        interface.append('}')
        print("\n".join(interface))
