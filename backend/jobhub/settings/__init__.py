# jobhub/settings/__init__.py
import os

ENV = os.getenv('DJANGO_ENV', 'dev')

if ENV == 'prod':
    from .prod import *
else:
    from .dev import *
