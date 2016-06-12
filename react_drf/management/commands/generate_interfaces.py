from django.core.management.base import AppCommand

from rest_framework import serializers

from react_drf import generator


class Command(AppCommand):
    def handle_app_config(self, app, **options):
        print("import {RestModel} from './schema';")
        for name, val in app.module.serializers.__dict__.items():
            try:
                if issubclass(val, serializers.ModelSerializer):
                    generator.generate_interface(val)
            except TypeError as e:
                pass
