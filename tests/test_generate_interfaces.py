from django.db import models
from django.test import TestCase

from enum import Enum

from rest_framework import serializers


def foo(enum):
    def __iter__(self):
        for index, (x, y) in enumerate(self.__members__.items()):
            yield x, y.value
    enum.__class__.__iter__ = __iter__
    return enum

def bar(enum):
    to_create = [(name, enum_value.value[0]) for name, enum_value in enum.__members__.items()]

    wrapped_enum = Enum('Animal', to_create)

    def __iter__(self):
        for _, enum_value in enum.__members__.items():
            yield enum_value.value[0], enum_value.value[1]

    wrapped_enum.__class__.__iter__ = __iter__
    return wrapped_enum


class CommandTests(TestCase):
    def setUp(self):

        class MyModel(models.Model):
            charfield = models.CharField(max_length=200)

        class MySerializer(serializers.ModelSerializer):
            class Meta:
                model = MyModel

        self.MySerializer = MySerializer

    def test_iterate_over_enum(self):

        @foo
        class Color(Enum):
            red = "My first choice"
            green = "My second choice"
            blue = "My third choice"

        class Widget(models.Model):
            @bar
            class STATUS(Enum):
                ACCEPTED = (1, 'Accepted')
                DENIED = (2 , 'Denied')

            color = models.CharField(choices=STATUS)

        print(list(Widget.STATUS))
        w = Widget(color=Widget.STATUS.ACCEPTED)
        print(w.color == Widget.STATUS.ACCEPTED)

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
