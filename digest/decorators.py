"""
@author: Dmitry Furzenko
@contact: dimonji@gmail.com
Base decorator for Http digest authentication
@attention: This decorator has to be last in the list of decorators
            @any_decorator
            @httpdigest
            def view(request):
                pass
"""
from functools import partial
from operator import isCallable

from decorator import decorator
from noodles.digest import HttpDigestAuthenticator
from noodles.http import Request


def _httpdigest(authenticator, f, *args, **kwargs):
    """


    :rtype : noodles.http.Response
    :param authenticator:
    :param f:
    :param args:
    :param kwargs:
    :return: :rtype: :raise:
    """
    if len(args) >= 1 and isinstance(args[0], Request):
        request = args[0]
    elif len(args) >= 2 and isinstance(args[1], Request):
        request = args[1]
    else:
        raise Exception("Neither args[0] nor args[1] is an HttpRequest.")
    if not authenticator.authenticate(request):
        return authenticator.build_challenge_response()
    response = f(*args, **kwargs)
    if hasattr(response, 'status') and response.status in [401, 403]:
        return authenticator.build_challenge_response()
    return response


def httpdigest(*args, **kwargs):
    """

    :param args:
    :param kwargs:
    May be used in one of three ways:
    * as a decorator factory (with the arguments being parameters to an
      instance of HttpDigestAuthenticator used to protect the decorated view)
    * as a decorator (protecting the decorated view with a default-constructed
      instance of HttpDigestAuthenticator)
    * as a decorator factory (with the argument being a pre-constructed
      HttpDigestAuthenticator instance used to protect the decorated view)
    """
    if len(args) == 1 and not kwargs and isCallable(args[0]):
        authenticator = HttpDigestAuthenticator()
        return decorator(partial(_httpdigest, authenticator), args[0])
    if len(args) == 1 and not kwargs and isinstance(args[0],
                                                    HttpDigestAuthenticator):
        authenticator = args[0]
    else:
        authenticator = HttpDigestAuthenticator(*args, **kwargs)

    def decor(f):
        return decorator(partial(_httpdigest, authenticator), f)
    return decor
