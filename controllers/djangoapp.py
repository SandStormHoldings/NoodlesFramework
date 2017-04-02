# -*- coding: utf-8 -*-
'''
filedesc: helper function to run django apps under noodles
'''
import os


try:
    from django.core.handlers.wsgi import WSGIHandler
except:
    raise DjangoImportError('Can\' import Django WSGIHandler. '
                            'Have you installed django?')

try:
    from config import DJANGO_SETTINGS
except:
    raise DjangoSettingsError('Django settings module is undefined')

os.environ['DJANGO_SETTINGS_MODULE'] = DJANGO_SETTINGS


def run_django(request, **kwargs):
    return WSGIHandler()


class DjangoImportError(Exception):
    pass


class DjangoSettingsError(Exception):
    pass
