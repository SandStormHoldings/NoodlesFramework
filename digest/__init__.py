"""
@author: Dmitry Furzenko
@contact: dimonji@gmail.com
Digest authentications decorator
"""
import random
import time
import urllib

import python_digest
from noodles.http import Response
from noodles.utils.helpers import get_config
from noodles.utils.logger import log
from lib.digest import SimpleDigestAuth


class DefaultLoginFactory(object):
    def confirmed_logins_for_user(self, user):
        return [login for login in
                [user.username, user.username.lower(), user.email,
                 user.email and user.email.lower()] if login]


class HttpDigestAuthenticator(object):
    """
    Http-digest authorization cls
    """
    def __init__(self, realm=None, timeout=None):
        self.realm = realm or get_config('DIGEST_REALM')
        self._account_storage = SimpleDigestAuth()
        self.timeout = timeout or get_config('DIGEST_TIMEOUT_IN_SECONDS')
        self.secret_key = get_config('SECRET_KEY')

    @staticmethod
    def contains_digest_credentials(request):
        return (request.headers.get('authorization') and
                python_digest.is_digest_credential(
                    request.headers.get('authorization')))

    def _store_nonce(self, nonce, request):
        """
        Store nonce string to session storage
        """

        if hasattr(request,'session'):
            prev_nonce = request.session.data.nonce
            request.session.data.nonce = nonce
            if prev_nonce == 'Logout':
                return False
        return True

    def authenticate(self, request):
        """
        Base authentication method, all checks here
        """
        if not request.headers.get('authorization'):
            return False
        if not python_digest.is_digest_credential(
                request.headers.get('authorization')):
            return False
        digest_response = python_digest.parse_digest_credentials(
            request.headers.get('authorization'))
        if not digest_response:
            log.debug('authentication failure: supplied digest credentials'
                      ' could not be parsed: "%s".'
                      % request.headers.get('authorization'))
            return False

        if not digest_response.username:
            return False

        if not digest_response.realm == self.realm:
            log.debug('authentication failure: supplied realm "%s"'
                      'does not match configured realm "%s".'
                      % (digest_response.realm, self.realm))
            return False

        if not python_digest.validate_nonce(
                digest_response.nonce, self.secret_key):
            log.debug('authentication failure: nonce validation failed.')
            return False
        partial_digest = self._account_storage.get_partial_digest(
            digest_response.username)

        if not partial_digest:
            log.debug('authentication failure: no partial digest available'
                      ' for user "%s".' % digest_response.username)
            return False

        calculated_request_digest = python_digest.calculate_request_digest(
            method=request.method, digest_response=digest_response,
            partial_digest=partial_digest)

        if not calculated_request_digest == digest_response.response:
            log.debug('authentication failure: supplied request digest'
                      'does not match calculated request digest.')
            return False

        if not python_digest.validate_uri(
                digest_response.uri, urllib.parse.unquote(request.path)):
            log.debug('authentication failure: digest authentication uri value'
                      '"%s" does not match value "%s" from HTTP'
                      'request line.' % (digest_response.uri, request.path))
            return False

        if not self._account_storage.is_admin(digest_response.username):
            log.debug('authentication failure: user not in operator admin.')
            return False

        if hasattr(request,'session') and request.session.data.nonce != digest_response.nonce:
            if (int(python_digest.get_nonce_timestamp(digest_response.nonce))
                    + self.timeout < time.time()):
                log.debug('authentication failure: attempt to establish'
                          ' a new session with a stale nonce.')
                return False
            if not self._store_nonce(digest_response.nonce, request):
                log.debug('authentication failure: attempt to establish'
                          ' a previously used or nonce count.')
                return False
        request.user = self._account_storage.get_by_login(
            digest_response.username)
        return True

    def build_challenge_response(self, stale=False):
        """
        If not auth show digest authentification form
        """
        opaque = ''.join([random.choice('0123456789ABCDEF')
                         for x in range(32)])  # IGNORE:W0612 @UnusedVariable
        response = Response()
        response.status = 401
        response.headerlist.append(('WWW-Authenticate',
                                    python_digest.build_digest_challenge(
                                        time.time(),
                                        self.secret_key,
                                        self.realm, opaque, stale)))
        return response
