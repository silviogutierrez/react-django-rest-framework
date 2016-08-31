from django.db import models
from django.test import TestCase

from enum import IntEnum, Enum, EnumMeta

from rest_framework import serializers, renderers, generics

import json


def foo(enum):
    def __iter__(self):
        for index, (x, y) in enumerate(self.__members__.items()):
            yield x, y.value
    enum.__class__.__iter__ = __iter__
    return enum

def integer_enum(enum):
    def __iter__(self):
        for index, (x, y) in enumerate(self.__members__.items()):
            yield x, y.value
    enum.__class__.__iter__ = __iter__
    return enum

def bar(enum):
    to_create = [(name, enum_value.value[0]) for name, enum_value in enum.__members__.items()]

    wrapped_enum = IntEnum('Animal', to_create)

    def __iter__(self):
        for _, enum_value in enum.__members__.items():
            yield enum_value.value[0], enum_value.value[1]

    wrapped_enum.__class__.__iter__ = __iter__
    return wrapped_enum


def stylize_class_name(name):
    if name.endswith('Serializer'):
        return name[:-10]
    else:
        return name


class XenumMeta(EnumMeta):
    def __new__(cls, name, bases, attrs):
        return super(XenumMeta, cls).__new__(cls, name, bases, attrs)

    def __iter__(self):
        for _, enum_value in self.__members__.items():
            yield enum_value, enum_value._label

    def __int__(self):
        assert False
        return self.value


class Xenum(IntEnum, metaclass = XenumMeta):
    def __new__(cls, label):
        value = len(cls.__members__) + 1
        obj = int.__new__(cls)
        obj._value_ = value
        obj._label = label
        return obj


import collections

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


class IntegerDenum(Denum):
    foo = (1, 'John Stamos')
    bar = (2, 'Dolph Lundgren')


class CommandTests(TestCase):
    def setUp(self):

        class MyModel(models.Model):

            JOHN_STAMOS = 1
            DOLPH_LUNDGREN = 2

            INTEGER_CHOICES = (
                (JOHN_STAMOS, 'John Stamos'),
                (DOLPH_LUNDGREN, 'Dolph Lundgren'),
            )

            LAWLWUT = 'USD'
            ALRIGHT = 'VEF'

            CHAR_CHOICES = (
                (LAWLWUT, 'Dollars'),
                (ALRIGHT, 'Bolivares'),
            )

            @integer_enum
            class INTEGER_ENUM(Enum):
                JOHN_STAMOS = 'John Stamos'
                DOLPH_LUNDGREN = 'Dolph Lundgren'

            class CHAR_ENUM(Enum):
                USD = 'Dollars'
                VEF = 'Bolivares'

            class INTEGER_XENUM(Xenum):
                JOHN_STAMOS = 'John Stamos'
                DOLPH_LUNDGREN = 'Dolph Lundgren'

            class INTEGER_DENUM(Denum):
                JOHN_STAMOS = (1, 'John Stamos')
                DOLPH_LUNDGREN = (2, 'Dolph Lundgren')

            charfield = models.CharField(max_length=200)
            integer_choice = models.IntegerField(choices=INTEGER_CHOICES)
            char_choice = models.IntegerField(choices=CHAR_CHOICES)
            integer_enum = models.IntegerField(choices=INTEGER_DENUM)
            char_enum = models.IntegerField(choices=CHAR_ENUM)
            related_model = models.ForeignKey('RelatedModel')

        class RelatedModel(models.Model):
            name = models.CharField(max_length=200)

        class RelatedModelSerializer(serializers.ModelSerializer):
            class Meta:
                model = RelatedModel

        class MyModelSerializer(serializers.ModelSerializer):
            related_model = RelatedModelSerializer()

            class Meta:
                model = MyModel

        class MyView(generics.ListCreateAPIView):
            serializer_class = MyModelSerializer
            queryset = MyModel.objects.all()

        self.MyModel = MyModel
        self.MyModelSerializer = MyModelSerializer
        self.MyView = MyView

    def test_choice_fields(self):
        m = self.MyModel(
            # integer_choice=self.MyModel.DOLPH_LUNDGREN,
            # char_choice=self.MyModel.ALRIGHT,
            integer_enum=self.MyModel.INTEGER_DENUM.DOLPH_LUNDGREN,
            # char_enum=self.MyModel.CHAR_ENUM.VEF,
        )
        # print(dict(self.MyModel.INTEGER_XENUM))
        self.assertEqual(m.get_integer_enum_display(), 'Dolph Lundgren')
        self.assertEqual(m.integer_enum, self.MyModel.INTEGER_DENUM.DOLPH_LUNDGREN)
        # print(renderers.JSONRenderer().render(self.MyModelSerializer(m).data))
        # self.assertEqual(self.MyModelSerializer(m).data['integer_enum'], 2)
        # print(int(m.integer_enum))
        # m.save()
        # import pdb
        # pdb.set_trace()


        class_name = stylize_class_name(self.MyModelSerializer.__name__)
        class_statics = []
        class_constants = []
        class_members = []
        class_methods = []

        for name, attribute in vars(self.MyModelSerializer.Meta.model).items():
            if type(attribute) is DenumMeta:
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

        for name, field in self.MyModelSerializer().fields.items():
            if isinstance(field, serializers.ModelSerializer):
                class_members.append('%s: %s;' %  (name,
                                                   stylize_class_name(field.__class__.__name__)))
            elif isinstance(field, serializers.ChoiceField):
                model_field = self.MyModelSerializer.Meta.model._meta.get_field(name)

                if type(model_field.choices) is DenumMeta:
                    class_members.append('%s: %s.%s;' % (name, class_name, model_field.choices.__name__))
                else:
                    class_members.append('%s: any;' % name)

                class_statics.append('static %s = %s;' % (name, json.dumps(list(model_field.choices))))

                class_methods.append("""
                get_%(name)s_display(): string {
                    const pair = %(class_name)s.%(name)s.find(choice => choice[0] == this.%(name)s);
                    return pair ? pair[1] : null;
                }""" %  {
                    'name': name,
                    'class_name': class_name,
                })
            else:
                class_members.append('%s: string;' % name)

        class_definition = """
        class RelatedModel {};

        class %(name)s {
            %(class_members)s
            %(class_methods)s
            %(class_statics)s
        }
        module %(name)s {
            %(class_constants)s
        }
        """ % {
            'name': class_name,
            'class_statics': "\n".join(class_statics),
            'class_constants': "\n".join(class_constants),
            'class_members': "\n".join(class_members),
            'class_methods': "\n".join(class_methods),
        }
        print(class_definition)
            # mapping = interface_field_mapping.get(type(field), 'any')
            # interface.append('    %s = %s;' % (name, mapping))


    """
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
    """
