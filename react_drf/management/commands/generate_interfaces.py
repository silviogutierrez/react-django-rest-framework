from django.core.management.base import NoArgsCommand

from rest_framework import serializers

from react_drf import generator


class Command(NoArgsCommand):
    def handle(self, **options):
        from react_drf.generator import writeExports
        writeExports()

        """
        print("/* tslint:disable */\nimport * as React from 'react';")
        for name, val in app.module.serializers.__dict__.items():
            try:
                if issubclass(val, serializers.ModelSerializer) and val.__name__ in ['RecipeSerializer', 'DaySerializer']:
                    # generator.generate_interface(val)
                    generator.generate_form(val)
            except TypeError as e:
                pass
        """
