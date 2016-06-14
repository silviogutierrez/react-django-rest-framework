from django.core.management.base import AppCommand

from rest_framework import serializers

from react_drf import generator


class Command(AppCommand):
    def handle_app_config(self, app, **options):
        print("/* tslint:disable */\nimport * as React from 'react';")
        for name, val in app.module.serializers.__dict__.items():
            try:
                if issubclass(val, serializers.ModelSerializer) and val.__name__ in ['RecipeSerializer', 'DaySerializer']:
                    # generator.generate_interface(val)
                    generator.generate_form(val)
            except TypeError as e:
                pass
