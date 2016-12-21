from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.core.exceptions import FieldDoesNotExist

from rest_framework import serializers
from rest_framework.metadata import SimpleMetadata

factory = RequestFactory()

import collections
import json
import re


class DenumMeta(type):
    @classmethod
    def __prepare__(self, name, bases):
        return collections.OrderedDict()

    def __new__(cls, name, bases, attrs):
        ATTRS_TO_EXCLUDE = ['__module__', '__qualname__']

        member_candidates = collections.OrderedDict()

        for attr_name, attr_value in attrs.items():
            if attr_name not in ATTRS_TO_EXCLUDE:
                member_candidates[attr_name] = attr_value

        actual_members = collections.OrderedDict()
        ordered = collections.OrderedDict()

        for member_name, (value, label) in member_candidates.items():
            actual_members[member_name] = value
            ordered[member_name] = label

        attrs['_ordered'] = ordered
        attrs.update(actual_members)

        return super().__new__(cls, name, bases, attrs)

    def __iter__(self):
        for member_name, label in self._ordered.items():
            yield getattr(self, member_name), label

    def members(self):
        for member_name, label in self._ordered.items():
            yield member_name, getattr(self, member_name)


class Denum(metaclass = DenumMeta):
    pass


def stylize_class_name(name):
    if name.endswith('Serializer'):
        return name[:-10]
    else:
        return name

patterns_to_export = []
class_definitions = ["class RelatedModel {}"]


def register_list_of_urls_for_export(patterns):
    patterns_to_export.extend(patterns)
    return patterns


def export(*input):
    if len(input) > 1:
        return register_list_of_urls_for_export(input)
    elif not len(input) == 1 or not issubclass(input[0], serializers.Serializer):
        assert False, "Export only supports url patterns or serializers."
    else:
        SourceSerializer = input[0]

    # return SourceSerializer
    class_name = stylize_class_name(SourceSerializer.__name__)
    class_schema = []
    class_statics = []
    class_constants = []
    class_constants_map = {}
    class_members = []
    class_methods = []

    if issubclass(SourceSerializer, serializers.ModelSerializer):
        for name, attribute in vars(SourceSerializer.Meta.model).items():
            if type(attribute) is DenumMeta:
                # If this is a string enum
                if type(list(attribute.members())[0][1]) == str:
                    enum_members = ["%s: '%s'," % (name, value) for name, value in attribute.members()]
                    # class_constants.append('%s: %s' % (name,
                    class_statics.append("""
                    static %(enum_name)s = {
                        %(enum_members)s
                    }
                    """ % {
                        'enum_name': name,
                        'enum_members': "\n".join(enum_members),
                    })

                    # enum_members = ["%s = '%s'," % (name, value) for name, value in attribute.members()]
                    value_members = ["'%s'" % value for name, value in attribute.members()]
                    value_definition = """
                    export type %(enum_name)s_def = %(enum_members)s;
                    """ % {
                        'enum_name': name,
                        'enum_members': "|".join(value_members),
                    }
                    class_constants.append(value_definition)
                    class_constants_map[name] = '%s_def' % name

                elif type(list(attribute.members())[0][1]) == int:
                    enum_members = ['%s = %s,' % (name, value) for name, value in attribute.members()]
                    # class_constants.append('%s: %s' % (name,
                    class_constants.append("""
                    export enum %(enum_name)s {
                        %(enum_members)s
                    }
                    """ % {
                        'enum_name': name,
                        'enum_members': "\n".join(enum_members),
                    })
                    class_constants_map[name] = name
                else:
                    assert False, "Unsupported enum type"

    request = factory.get('/')
    request.user = get_user_model()()
    serializer_instance = SourceSerializer(read_only=True, context={'request': request})

    for name, field in serializer_instance.fields.items():
        if name == 'units':
            continue

        if isinstance(field, serializers.ListSerializer) and isinstance(field.child, serializers.ModelSerializer):
            class_members.append('%s: %s[];' %  (name,
                                            stylize_class_name(field.child.__class__.__name__)))
        elif isinstance(field, serializers.ModelSerializer):
            field_type = stylize_class_name(field.__class__.__name__)

            if (field.allow_null):
                field_type += '|null'

            class_members.append('%s: %s;' %  (name,
                                            field_type))
        elif isinstance(field, serializers.ChoiceField):
            try:
                model_field = SourceSerializer.Meta.model._meta.get_field(name)
            except FieldDoesNotExist:
                continue
                # Currently skipping serializer only choice fields.

            if type(model_field.choices) is DenumMeta:
                class_members.append('%s: %s.%s;' % (name, class_name, class_constants_map[model_field.choices.__name__]))
            else:
                class_members.append('%s: any;' % name)

            # class_statics.append('static %s = %s;' % (name, json.dumps(list(model_field.choices))))

            class_methods.append("""
            get_%(name)s_display(): string|null {
                const choice = %(class_name)s.schema.%(name)s.choices.find(({display_name, value}: {display_name: string; value: string}) => value == this.%(name)s);
                return choice ? choice.display_name : null;
            }""" %  {
                'name': name,
                'class_name': class_name,
            })
        elif isinstance(field, serializers.IntegerField):
            class_members.append('%s: number;' % name)
        elif isinstance(field, serializers.PrimaryKeyRelatedField):
            # TODO: primary key might not be a number.
            if (field.allow_null):
                class_members.append('%s: number|null;' % name)
            else:
                class_members.append('%s: number;' % name)
        elif isinstance(field, serializers.BooleanField):
            class_members.append('%s: boolean;' % name)
        elif isinstance(field, serializers.ManyRelatedField):
            class_members.append('%s: number[];' % name)
        else:
            if (field.allow_null):
                class_members.append('%s: string|null;' % name)
            else:
                class_members.append('%s: string;' % name)

    metadata_handler = SimpleMetadata()
    serializer_metadata = metadata_handler.get_serializer_info(serializer_instance)

    for field_name, field in serializer_metadata.items():
        field['name'] = field_name
        casted = json.dumps(field)

        casted = re.sub(r'"name": ("(\w+)")', r'"name": \1 as \1', casted)
        casted = casted.replace('"string"', '"string" as "string"')
        casted = casted.replace('"email"', '"email" as "email"')
        casted = casted.replace('"decimal"', '"decimal" as "decimal"')
        casted = casted.replace('"integer"', '"integer" as "integer"')
        casted = casted.replace('"boolean"', '"boolean" as "boolean"')
        casted = casted.replace('"choice"', '"choice" as "choice"')
        class_schema.append('%s: %s,' % (field_name, casted))

    class_definition = """
    /*
    export class %(name)s {
        constructor(data: %(name)s.Data) {
            Object.assign(this, data);
        }

        %(class_members)s
        %(class_methods)s
        %(class_statics)s

        static schema = {
            %(class_schema)s
        };
    }
    */

    export interface %(name)s {
        %(class_members)s
    }

    export namespace %(name)s {
        export const schema = {
            %(class_schema)s
        };
        %(class_constants)s
        /*
        export interface Data {
            %(class_members)s
        }
        */
    }
    """ % {
        'name': class_name,
        'class_statics': "\n".join(class_statics),
        'class_constants': "\n".join(class_constants),
        'class_members': "\n".join(class_members),
        'class_methods': "\n".join(class_methods),
        'class_schema': "\n".join(class_schema),
    }

    class_definitions.append(class_definition)
    return SourceSerializer


def process_patterns():

    exported_views = []

    from rest_framework import mixins
    from django.core.urlresolvers import reverse

    for pattern in patterns_to_export:
        view_class = pattern.callback.view_class
        serializer_class = view_class.serializer_class

        model_name = stylize_class_name(serializer_class.__name__)
        view_name = view_class.__name__
        import pdb
        pdb.set_trace()
        # print(reverse(pattern.name))

        if issubclass(view_class, mixins.ListModelMixin):
            exported_views.append("""

export const fetchFoods = () => {
    return (dispatch: Dispatch) => {
        dispatch({
            type: '%(FETCH_REQUEST)s',
        });

        return api.get<%(model_name)s[]>('/api/foods/').then(response => {
            dispatch({
                type: '%(FETCH_SUCCESS)s',
                foods: response.data,
            });
            return response.data;
        });
    };
};
                         """ % {
                'model_name': model_name,
                'FETCH_REQUEST': 'FETCH_%s_REQUEST' % view_name,
                'FETCH_SUCCESS': 'FETCH_%s_SUCCESS' % view_name,
                'FETCH_ERROR': 'FETCH_%s_ERROR' % view_name,
            })

    print(exported_views)


def writeExports():
    from django.conf import settings
    import json
    import os

    process_patterns()

    existing_deserialized_reference = None
    destination = os.path.join(settings.BASE_DIR, 'react/exports.ts')

    # See if we already have exports.
    if os.path.isfile(destination):
        with open(destination, 'r') as f:
            # The last line is a comment with a serialized structure.
            # Remove the '// ' and deserialize for comparison.
            try:
                existing_deserialized_reference = json.loads(f.readlines()[-1][3:])
            except Exception as e:
                pass


    # Only write if the exports are not exactly the same.
    if (class_definitions != existing_deserialized_reference):
        serialized_reference = "\n// %s" % json.dumps(class_definitions)
        contents_to_write = "\n".join(class_definitions) + serialized_reference

        with open(destination, 'w') as f:
            f.write(contents_to_write)


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
    request.user = get_user_model()()

    serializer_instance = SourceSerializer(context={'request': request})
    metadata_handler = SimpleMetadata()
    serializer_metadata = metadata_handler.get_serializer_info(serializer_instance)

    context = {
        'name': SourceSerializer.__name__.replace('Serializer', 'Form'),
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
