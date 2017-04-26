# -*- coding: utf-8 -*-
'''
filedesc: Module for extending webob Request and Response classes
'''
# to use in our server application
import json

import webob
from mako.template import Template
from noodles.utils.datahandler import datahandler
from noodles.utils.logger import log


SET_COOKIES = '__set_cookies'
UNSET_COOKIES = '__unset_cookies'


class Request(webob.Request):
    " Request object wrapper fo adding session handling and other features "
    def __init__(self, env):
        super(Request, self).__init__(env)


class BaseResponse(webob.Response):
    " Just wrapper, may be implemnt cookies there, may be somthing else )) "
    is_noodles_response = True  # for check if it really noodles response


class Response(BaseResponse):
    " Simple response class with 200 http header status "
    def __init__(self, body=''):
        super(Response, self).__init__()
        # Set standard response attributes
        self.status = 200  # 200 OK, it's default, but anyway...
        self.headerlist = [('Content-type', 'text/html')]
        self.charset = 'utf-8'
        if isinstance(body, str):
            self.body = body
        else:
            self.text = body


class Redirect(BaseResponse):
    " Redirect response "
    def __init__(self, redirect_url, cookie_dict=None):
        super(Redirect, self).__init__()
        self.status = 302
        self.headerlist = [('Content-type', 'text/html')]
        self.charset = 'utf-8'
        #TODO: serg
        if cookie_dict:
            for cookie in cookie_dict:
                self.set_cookie(str(cookie), str(cookie_dict.get(cookie)))
        self.location = redirect_url


class Error403(BaseResponse):
    " Simple Http 403 error implementation "
    def __init__(self, error_body=''):
        super(Error403, self).__init__()
        self.status = 403
        self.headerlist = [('Content-type', 'text/html')]
        self.charset = 'utf-8'
        self.text = unicode(error_body)


class Error404(BaseResponse):
    " Simple Http 404 error implementation "
    def __init__(self, error_body=''):
        super(Error404, self).__init__()
        self.status = 404
        self.headerlist = [('Content-type', 'text/html')]
        self.charset = 'utf-8'
        self.text = unicode(error_body)


class Error500(BaseResponse):
    """
    HTTP 500 error response with server traceback if DEBUG
    """
    def __init__(self, ex=None, tb=None):
        super(Error500, self).__init__()
        self.status = 500
        self.headerlist = [('Content-type', 'text/html')]
        self.charset = 'utf-8'
        if not tb:
            tb = "Please, load this page later"
        if ex:
            ex = ex.__repr__()
        else:
            ex = "Sorry, an error occured"
        error_500_template = """
                            <h1>500 error</h1>
                            <div style="font-size:125%">
                                ${ex|h}
                            </div>

                            <div style="margin-top: 20px"><pre>
                                ${tb|h}
                            </pre></div>
                            """
        self.body = Template(error_500_template).render(ex=ex.__repr__(),
                                                        tb=tb).encode('utf-8')


class XResponse(BaseResponse):
    " Ajax response, return a JSON object "
    def __init__(self, response_dict):
        # Set standard response attributes
        super(XResponse, self).__init__()
        self.status = 200  # 200 OK, it's default, but anyway...
        self.headerlist = [('Content-type', 'application/x-javascript')]
        self.charset = 'utf-8'

        # Set and unset cookies
        # Set cookies
        try:
            set_cookies_dict = response_dict.get(SET_COOKIES)
        except:
            return None
        log.debug('response_dict2 is %s. Set-cookies dict is %s'
                  % (response_dict, set_cookies_dict))
        if set_cookies_dict:
            for cookie in set_cookies_dict:
                log.debug('Try to set cookie %s to value %s'
                          % (cookie, set_cookies_dict[cookie]))
                self.set_cookie(cookie, str(set_cookies_dict[cookie]))
            response_dict.pop(SET_COOKIES)

        # Unset cookies
        unset_cookies_dict = response_dict.get(UNSET_COOKIES)
        if unset_cookies_dict:
            for cookie in unset_cookies_dict:
                self.delete_cookie(cookie)
            response_dict.pop(UNSET_COOKIES)
        self.body = json.dumps(response_dict, default=datahandler,indent=True)


# Specify decorator for ajax response controller functions
# Usage:
#
#   @ajax_response
#   def some_controller(request):
#       # some code
#       return resonse_dict # dictionary object with response values
def ajax_response(func):
    def gen(**kwargs):
        resp_dict = func(**kwargs)
        return XResponse(resp_dict)
    return gen
