from django.contrib.auth import get_user_model
from django.test import RequestFactory

from rest_framework import serializers

factory = RequestFactory()


def generate_interface(SourceSerializer):
        request = factory.get('/')
        request.user = get_user_model()

        serializer_instance = SourceSerializer(context={'request': request})
        interface = [
            'export abstract class %s extends RestModel {' % type(serializer_instance).__name__,
        ]

        interface_field_mapping = {
            serializers.IntegerField: 'number',
            serializers.CharField: 'string',
        }
        for name, field in serializer_instance.fields.items():
            mapping = interface_field_mapping.get(type(field), 'any')
            interface.append('    %s: %s;' % (name, mapping))
        interface.append('}')
        print("\n".join(interface))


def generate_form(SourceSerializer):
        request = factory.get('/')
        request.user = get_user_model()

        serializer_instance = SourceSerializer(context={'request': request})
        interface = [
            'export abstract class %s extends RestModel {' % type(serializer_instance).__name__,
        ]

        interface_field_mapping = {
            serializers.IntegerField: 'number',
            serializers.CharField: 'string',
        }
        for name, field in serializer_instance.fields.items():
            mapping = interface_field_mapping.get(type(field), 'any')
            interface.append('    %s: %s;' % (name, mapping))
        interface.append('}')
        print("\n".join(interface))
