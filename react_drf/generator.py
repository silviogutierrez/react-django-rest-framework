from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory

from rest_framework import serializers
from rest_framework.metadata import SimpleMetadata

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
    metadata_handler = SimpleMetadata()
    serializer_metadata = metadata_handler.get_serializer_info(serializer_instance)

    context = {
        'optional_fields': [],
        'fields': [],
    }

    mapping = {
        'string': 'string',
        'boolean': 'boolean',
        'integer': 'number',
    }

    for field_name, field in serializer_metadata.items():
        if not field.get('read_only', False):
            field_type = mapping.get(field['type'], 'any')

            context['fields'].append({
                'name': field_name,
                'type': field_type,
            })

            if not field.get('required', True):
                context['optional_fields'].append(field_name)

    print(render_to_string('form.tsx', context))
