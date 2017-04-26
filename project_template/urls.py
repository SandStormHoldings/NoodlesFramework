# -*- coding: utf-8 -*-
"""
filedesc: default url mapping
"""
from routes import Mapper
from config import DEBUG
from noodles.utils import urlmap
from routes.route import Route
import os


def get_map():
    " This function returns mapper object for dispatcher "
    map = Mapper()
    # Add routes here
    urlmap(map, [
        ('/', 'controllers#index'),
        #('/route/url', 'controllerName.actionName')
    ])

    # Old style map connecting
    #map.connect('Route_name', '/route/url', controller='controllerName',
    #action='actionName')

    if DEBUG:
        r = [Route(None, '/{path_info:.*}',
              controller='noodles.utils.static',
              action='index',
              path=os.path.join(os.getcwd(), 'static'),
              auth=True)]

        map.extend(r, '/static')

    return map
