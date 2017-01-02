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

def stylize_view_name(name):
    if name.endswith('Detail'):
        return name[:-6]
    if name.endswith('List'):
        return name[:-4] + 's'
    else:
        return name

def snake_case(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def constant_case(name):
    return snake_case(name).upper()

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
        camel_case_model_name = model_name[0].lower() + model_name[1:]

        view_name = stylize_view_name(view_class.__name__)
        constant_name = constant_case(view_name)
        camel_case_name = view_name[0].lower() + view_name[1:]

        key_name = view_class.lookup_field if view_class.lookup_field != 'pk' else 'id'
        key_type = 'string' if view_class.lookup_field != 'pk' else 'number'

        by_key_name = '%ssById' % camel_case_model_name
        list_name = '%sList' % camel_case_model_name

        reverse_args = ['%s' % (position * 1000) for key, position in pattern.regex.groupindex.items()]
        url_with_placeholders = reverse(pattern.name, args=reverse_args)
        function_args = []

        for key, position in pattern.regex.groupindex.items():
            function_args.append('%s: string|number' % key)
            url_with_placeholders = url_with_placeholders.replace('%s' % (position * 1000), '${%s}' % key)

        # print(reverse(pattern.name))
        base_context = {
            'lookup_field': view_class.lookup_field,
            'args': ', '.join(function_args),
            'view_name': view_name,
            'model_name': model_name,
            'camel_case_name': camel_case_name,
            'url': url_with_placeholders,
            'list_name': list_name,
            'by_key_name': by_key_name,
            'key_name': key_name,
        }

        if issubclass(view_class, mixins.CreateModelMixin):
            context = {**base_context, **dict(
                view_name=view_class.__name__[:-4],
                FETCH_REQUEST='CREATE_%s_REQUEST' % constant_case(view_class.__name__[:-4]),
                FETCH_SUCCESS='CREATE_%s_SUCCESS' % constant_case(view_class.__name__[:-4]),
                FETCH_ERROR='CREATE_%s_ERROR' % constant_case(view_class.__name__[:-4]),
                camel_case_name = model_name[0].lower() + model_name[1:]
            )}

            view_actions = [
                """{type: '%(FETCH_REQUEST)s', %(camel_case_name)s: %(model_name)s}""" % context,
                """{type: '%(FETCH_SUCCESS)s', %(camel_case_name)s: %(model_name)s}""" % context,
                """{type: '%(FETCH_ERROR)s', errors: any}""" % context,
            ]

            schema = [
                '%s: {} as {[%s: %s]: %s}' % (by_key_name, key_name, key_type, model_name),
                '%s: [] as number[]' % (list_name),
            ]

            reducer_definition = """
case '%(FETCH_SUCCESS)s': {

    const %(by_key_name)s = Object.assign({}, state.%(by_key_name)s, {[action.%(camel_case_name)s.%(key_name)s]: action.%(camel_case_name)s});
    return Object.assign({}, state, {%(by_key_name)s});
}
            """ % context
            view_definition = """

export const create%(view_name)s = (item: %(model_name)s) => {
    const %(lookup_field)s = item.%(key_name)s;

    return (dispatch: Dispatch) => {
        dispatch({
            type: '%(FETCH_REQUEST)s',
            %(camel_case_name)s: item,
        });

        return api.post<%(model_name)s>(`%(url)s`, item).then(response => {
            dispatch({
                type: '%(FETCH_SUCCESS)s',
                %(camel_case_name)s: response.data,
            });
            return response.data;
        });
    };
};""" % context
            exported_views.append({
                'schema': schema,
                'reducer': reducer_definition,
                'definition': view_definition,
                'actions': view_actions,
            })
        if issubclass(view_class, mixins.DestroyModelMixin):
            context = {**base_context, **dict(
                FETCH_REQUEST='DELETE_%s_REQUEST' % constant_name,
                FETCH_SUCCESS='DELETE_%s_SUCCESS' % constant_name,
                FETCH_ERROR='DELETE_%s_ERROR' % constant_name,
            )}

            view_actions = [
                """{type: '%(FETCH_REQUEST)s', %(camel_case_name)s: %(model_name)s}""" % context,
                """{type: '%(FETCH_SUCCESS)s', %(camel_case_name)s: %(model_name)s}""" % context,
                """{type: '%(FETCH_ERROR)s', errors: any}""" % context,
            ]

            schema = [
                '%s: {} as {[%s: %s]: %s}' % (by_key_name, key_name, key_type, model_name),
                '%s: [] as number[]' % (list_name),
            ]
            reducer_definition = """
            // Currently we do not delete objects from the store.
            """ % context
            view_definition = """

export const delete%(view_name)s = (item: %(model_name)s) => {
    const %(lookup_field)s = item.%(key_name)s;

    return (dispatch: Dispatch) => {
        dispatch({
            type: '%(FETCH_REQUEST)s',
            %(camel_case_name)s: item,
        });

        return api.delete<%(model_name)s>(`%(url)s`).then(response => {
            dispatch({
                type: '%(FETCH_SUCCESS)s',
                %(camel_case_name)s: item,
            });
        });
    };
};
                        """ % context
            exported_views.append({
                'schema': schema,
                'reducer': reducer_definition,
                'definition': view_definition,
                'actions': view_actions,
            })

        if issubclass(view_class, mixins.UpdateModelMixin):
            context = {**base_context, **dict(
                FETCH_REQUEST='UPDATE_%s_REQUEST' % constant_name,
                FETCH_SUCCESS='UPDATE_%s_SUCCESS' % constant_name,
                FETCH_ERROR='UPDATE_%s_ERROR' % constant_name,
            )}

            view_actions = [
                """{type: '%(FETCH_REQUEST)s', %(camel_case_name)s: %(model_name)s}""" % context,
                """{type: '%(FETCH_SUCCESS)s', %(camel_case_name)s: %(model_name)s}""" % context,
                """{type: '%(FETCH_ERROR)s', errors: any}""" % context,
            ]
            schema = [
                '%s: {} as {[%s: %s]: %s}' % (by_key_name, key_name, key_type, model_name),
                '%s: [] as number[]' % (list_name),
            ]
            reducer_definition = """
case '%(FETCH_SUCCESS)s': {

    const %(by_key_name)s = Object.assign({}, state.%(by_key_name)s, {[action.%(camel_case_name)s.%(key_name)s]: action.%(camel_case_name)s});
    return Object.assign({}, state, {%(by_key_name)s});
}
            """ % context
            view_definition = """

export const update%(view_name)s = (item: %(model_name)s) => {
    const %(lookup_field)s = item.%(key_name)s;

    return (dispatch: Dispatch) => {
        dispatch({
            type: '%(FETCH_REQUEST)s',
            %(camel_case_name)s: item,
        });

        return api.put<%(model_name)s>(`%(url)s`, item).then(response => {
            dispatch({
                type: '%(FETCH_SUCCESS)s',
                %(camel_case_name)s: response.data,
            });
            return response.data;
        });
    };
};
                        """ % context
            exported_views.append({
                'schema': schema,
                'reducer': reducer_definition,
                'definition': view_definition,
                'actions': view_actions,
            })
        if issubclass(view_class, mixins.RetrieveModelMixin):
            context = {**base_context, **dict(
                FETCH_REQUEST='FETCH_%s_REQUEST' % constant_name,
                FETCH_SUCCESS='FETCH_%s_SUCCESS' % constant_name,
                FETCH_ERROR='FETCH_%s_ERROR' % constant_name,
            )}
            view_actions = [
                """{type: '%(FETCH_REQUEST)s'}""" % context,
                """{type: '%(FETCH_SUCCESS)s', %(camel_case_name)s: %(model_name)s}""" % context,
                """{type: '%(FETCH_ERROR)s', errors: any}""" % context,
            ]
            schema = [
                '%s: {} as {[%s: %s]: %s}' % (by_key_name, key_name, key_type, model_name),
                '%s: [] as number[]' % (list_name),
            ]
            reducer_definition = """
case '%(FETCH_SUCCESS)s': {

    const %(by_key_name)s = Object.assign({}, state.%(by_key_name)s, {[action.%(camel_case_name)s.%(key_name)s]: action.%(camel_case_name)s});
    return Object.assign({}, state, {%(by_key_name)s});
}
            """ % context

            view_definition = """

export const fetch%(view_name)s = (%(args)s) => {
    return (dispatch: Dispatch) => {
        dispatch({
            type: '%(FETCH_REQUEST)s',
        });

        return api.get<%(model_name)s>(`%(url)s`).then(response => {
            dispatch({
                type: '%(FETCH_SUCCESS)s',
                %(camel_case_name)s: response.data,
            });
            return response.data;
        });
    };
};
                        """ % context
            exported_views.append({
                'schema': schema,
                'reducer': reducer_definition,
                'definition': view_definition,
                'actions': view_actions,
            })

        if issubclass(view_class, mixins.ListModelMixin):
            context = {**base_context, **dict(
                FETCH_REQUEST='FETCH_%s_REQUEST' % constant_name,
                FETCH_SUCCESS='FETCH_%s_SUCCESS' % constant_name,
                FETCH_ERROR='FETCH_%s_ERROR' % constant_name,
            )}
            view_actions = [
                """{type: '%(FETCH_REQUEST)s'}""" % context,
                """{type: '%(FETCH_SUCCESS)s', %(camel_case_name)s: %(model_name)s[]}""" % context,
                """{type: '%(FETCH_ERROR)s', errors: any}""" % context,
            ]
            schema = [
                '%s: {} as {[%s: %s]: %s}' % (by_key_name, key_name, key_type, model_name),
                '%s: [] as number[]' % (list_name),
            ]
            reducer_definition = """
case '%(FETCH_SUCCESS)s': {
    let %(by_key_name)s = Object.assign({}, state.%(by_key_name)s);
    const %(list_name)s = action.%(camel_case_name)s.map(item => {
        %(by_key_name)s[item.%(key_name)s] = item;
        return item.%(key_name)s;
    });
    return Object.assign({}, state, {%(by_key_name)s, %(list_name)s});
}
            """ % context
            view_definition = """

export const fetch%(view_name)s = (%(args)s) => {
    return (dispatch: Dispatch) => {
        dispatch({
            type: '%(FETCH_REQUEST)s',
        });

        return api.get<%(model_name)s[]>(`%(url)s`).then(response => {
            dispatch({
                type: '%(FETCH_SUCCESS)s',
                %(camel_case_name)s: response.data,
            });
            return response.data;
        });
    };
};
                        """ % context
            exported_views.append({
                'schema': schema,
                'reducer': reducer_definition,
                'definition': view_definition,
                'actions': view_actions,
            })

    return exported_views


def writeExports():
    from django.conf import settings
    import json
    import os

    to_export = {
        'views': process_patterns(),
        'models': class_definitions,
    }

    existing_deserialized_reference = None
    destination = os.path.join(settings.BASE_DIR, 'client/exports.ts')

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
    if True or (to_export != existing_deserialized_reference):
        serialized_reference = "\n// %s" % json.dumps(to_export)

        # This flattens an array of arrays. See
        # See: http://stackoverflow.com/a/952946
        actions = sum([view['actions'] for view in to_export['views']], [])
        state = set(sum([view['schema'] for view in to_export['views']], []))

        views = [view['definition'] for view in to_export['views']]
        reducers = [view['reducer'] for view in to_export['views']]

        reducer = """

export const initialState = {
    %s
};

export const reducer = <T extends typeof initialState>(state: T, action: Action): T => {
    switch (action.type) {
        %s
        default: {
            return state;
        }
    }
}

""" % (",\n".join(state), "\n".join(reducers))

        contents_to_write = ""
        contents_to_write += "import {Action, Dispatch} from 'client/reducer'\n";
        contents_to_write += "import {api} from 'client/api'\n";
        contents_to_write += "export type Actions = %s" % "|".join(actions)
        contents_to_write += reducer
        contents_to_write += "\n".join(views)
        contents_to_write += "\n"
        contents_to_write += "\n".join(to_export['models'])
        contents_to_write += serialized_reference

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
