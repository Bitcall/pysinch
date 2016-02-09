"""
Created on: Feb 6, 2016
Company: Bitcall AB
"""

# Standard imports
from urllib2 import Request, urlopen
from base64 import b64encode, b64decode
from json import loads, dumps
from datetime import datetime
from platform import uname
from hashlib import sha256, md5
from hmac import new as new_hmac
from sys import version_info


# TODO: docstrings
# TODO: slots
# TODO: unittests
# TODO: authorization vs authorisation
# TODO: note about required JSON payload even if empty


def smart_caching(function):
    """
    :param function: Method of class SinchAPI that will trigger instance
    refresh if out-dated. Instance is very similar to session in nature.
    :return: Decorated method of class SinchAPI.
    """

    def _wrapped(self, *args, **kwargs):
        if (
            not self.cached_instance_authorization['id']
        ) or (
            (
                datetime.utcnow() - self.cached_instance_authorization[
                    'datetime'
                ]
            ).seconds >= self.cached_instance_authorization['duration']
        ):
            response = self.sinch_api_request(
                api_subdomain=self.subdomain_api,
                path='/instance',
                data={
                    'authorization': self.cached_user_authorization,
                    'version': {
                        'os': self.cached_os_deatils,
                        'platform': self.cached_platform_details
                    }
                },
                authorization_scheme='user'
            )

            self.cached_instance_authorization['secret'] = response['secret']
            self.cached_instance_authorization['id'] = response['id']
            # TODO: explain about this
            self.cached_instance_authorization['duration'] = response[
                'expiresIn'
            ] - 30
            self.cached_instance_authorization['datetime'] = datetime.utcnow()

            if not self.cached_organisation_id:
                self.cached_organisation_id = self.sinch_api_request(
                    api_subdomain=self.subdomain_api,
                    data={},
                    path='/organisations',
                    authorization_scheme='instance',
                    method='GET'
                )[0]['id']
        return function(self, *args, **kwargs)
    return _wrapped


class SinchAPI(object):
    """ Represents encapsulated REST API along with some utility methods. """

    def __init__(  # IGNORE:too-many-arguments
        self, app_key, app_secret, email, password, number_administration_key
    ):
        """
        :param app_key:
        :param app_secret:
        :param email:
        :param password:
        :param number_administration_key:
        :return:
        """

        self.app_key = app_key

        self.url_prefix_path = '/v1'
        self.url_prefix_template = 'https://%s.sinch.com%s' % (
            '%s', self.url_prefix_path
        )
        self.subdomain_callingapi = 'callingapi'
        self.subdomain_userapi = 'userapi'
        self.subdomain_api = 'api'
        self.subdomain_portalapi = 'portalapi'

        self.cached_basic_authorization = (
            'basic %s' % b64encode(
                'application\\%s:%s' % (app_key, app_secret)
            )
        )
        # Number administration logic uses public authorization scheme
        self.cached_public_authorization = (
            'Application %s' % number_administration_key
        )
        self.cached_user_authorization = 'User %s' % self.sinch_api_request(
            api_subdomain=self.subdomain_userapi,
            path='/users/email/%s/authentication' % email,
            data={'password': password},
            authorization_scheme='public'
        )['authorization']
        self.cached_instance_authorization = {
            'secret': None, 'duration': 0, 'datetime': None, 'id': None
        }

        self.cached_organisation_id = None

        self.cached_os_deatils = uname()[0]
        self.cached_platform_details = (
            'Python %s.%s.%s' % (
                version_info.major, version_info.minor, version_info.micro
            )
        )

    @staticmethod
    def _generate_content_md5(content):
        if not content:
            return ''
        else:
            return b64encode(md5(content).digest())

    def _form_string_to_sign(self, path, request, content_md5):
        return '%s\n%s\n%s\n%s\n%s' % (
            request.get_method(),
            content_md5,
            'application/json',
            'x-timestamp:%s' % request.get_header('X-timestamp'),  # TODO: Note about capitalise
            '%s%s' % (self.url_prefix_path, path)
        )

    def sinch_api_request(  # IGNORE:too-many-arguments
        self,
        api_subdomain,
        path,
        data=None,
        method=None,
        authorization_scheme='basic'
    ):
        request = Request(
            '%s%s' % (self.url_prefix_template % api_subdomain, path)
        )

        request.add_header(
            'X-Timestamp', '%sZ' % datetime.utcnow().isoformat()
        )

        # TODO: important note about method before auth
        if method:
            request.get_method = lambda: method

        if data is not None:
            request.data = dumps(data)
            request.add_header('Content-type', 'application/json')

        if authorization_scheme == 'basic':
            request.add_header(
                'Authorization', self.cached_basic_authorization
            )
        elif authorization_scheme == 'public':
            request.add_header(
                'Authorization', self.cached_public_authorization
            )
        elif authorization_scheme == 'user':
            request.add_header('Authorization', self.cached_user_authorization)
        elif authorization_scheme == 'instance':
            request.add_header(
                'Authorization',
                'Instance %s:%s' % (
                    self.cached_instance_authorization['id'],
                    b64encode(
                        new_hmac(
                            b64decode(
                                self.cached_instance_authorization['secret']
                            ),
                            msg=unicode(
                                self._form_string_to_sign(
                                    path,
                                    request,
                                    self._generate_content_md5(request.data)
                                )
                            ),
                            digestmod=sha256
                        ).digest()
                    )
                )
            )
        else:
            # TODO: exception about unknown auth scheme
            pass

        response = urlopen(request).read()
        if response:
            return loads(response)

    def get_numbers(self):
        """ Get numbers along with applications they have been assigned to. """
        return self.sinch_api_request(
            api_subdomain=self.subdomain_callingapi,
            path='/configuration/numbers/'
        )['numbers']

    def assign_number(self, number):
        # TODO: check if number exists
        # TODO: E.164 format
        # TODO: reassigning all numbers, including existing, because of possibility
        #       to overwrite them - docs state this for another similar API - if this is not the case
        #       remove redundant request to speed up things

        # FIXME: does not work
        self.sinch_api_request(
            api_subdomain=self.subdomain_callingapi,
            path='/configuration/numbers/',
            data={'numbers': (number,)}
        )

    def get_callbacks(self):
        return self.sinch_api_request(
            api_subdomain=self.subdomain_callingapi,
            path='/configuration/callbacks/applications/%s' % self.app_key
        )['url']

    def set_callbacks(self, primary, fallback=None):
        self.sinch_api_request(
            api_subdomain=self.subdomain_callingapi,
            path='/configuration/callbacks/applications/%s' % self.app_key,
            data={'url': {'primary': primary, 'fallback': fallback}}
        )

    def query_number(self, number):
        # TODO: E.164 format
        return self.sinch_api_request(
            api_subdomain=self.subdomain_callingapi,
            path='/calling/query/number/%s' % number
        )['number']

    def get_call_result(self, call_id):
        # TODO: validate call_id
        # FIXME: returns: None
        return self.sinch_api_request(
            api_subdomain=self.subdomain_callingapi,
            path='/calls/id/%s' % call_id
        )

    def manage_call(
        self, call_id, message_text, message_recordings, action, locale='en-US'
    ):
        # TODO: validate arguments
        # TODO: This method can only be used for calls that are originating from or terminating to the PSTN network.

        instructions = {'Instructions': [], 'Action': {}}

        if message_recordings:
            if isinstance(message_recordings, str):
                message_recordings = (message_recordings,)

            instructions['Instructions'].append(
                {
                    'name': 'PlayFiles',
                    'ids': tuple(
                        message_recordings
                        for message_recordings in message_recordings
                    ),
                    'locale': locale
                }
            )

        if message_text:
            instructions['Instructions'].append(
                {'name': 'Say', 'text': message_text, 'locale': locale}
            )

        if action:
            instructions['Action']['name'] = action

        self.sinch_api_request(
            api_subdomain=self.subdomain_callingapi,
            path='/calls/id/%s' % call_id,
            data=instructions,
            method='PATCH'
        )

    def get_conferences(self, conference_id):
        return self.sinch_api_request(
            api_subdomain=self.subdomain_callingapi,
            path='/conferences/id/%s' % conference_id
        )['participants']

    def toggle_participant_microphone(
        self, conference_id, call_id, mute=False
    ):
        self.sinch_api_request(
            api_subdomain=self.subdomain_callingapi,
            path='/conferences/id/%s/%s' % (conference_id, call_id),
            data={'command': 'mute' if mute else 'unmute'},
            method='PATCH'
        )

    def kick_participant(self, conference_id, call_id):
        self.sinch_api_request(
            api_subdomain=self.subdomain_callingapi,
            path='/conferences/id/%s/%s' % (conference_id, call_id),
            method='DELETE'
        )

    def kick_all_participants(self, conference_id):
        self.sinch_api_request(
            api_subdomain=self.subdomain_callingapi,
            path='/conferences/id/%s' % conference_id,
            method='DELETE'
        )

    @smart_caching
    def get_available_numbers(self):
        return self.sinch_api_request(
            api_subdomain=self.subdomain_portalapi,
            path=(
                '/organisations/id/%s/numbers/shop'
                %
                self.cached_organisation_id
            ),
            data={},
            authorization_scheme='instance',
            method='GET'
        )

    @smart_caching
    def reserve_number(self, group_id, quantity):
        return self.sinch_api_request(
            api_subdomain=self.subdomain_portalapi,
            path=(
                '/organisations/id/%s/numbers/shop'
                %
                self.cached_organisation_id
            ),
            data={"groupId": group_id, "quantity": quantity},
            authorization_scheme='instance',
            method='PUT'
        )['referenceId']

    @smart_caching
    def checkout_reserved_numbers(self, reference_id):
        self.sinch_api_request(
            api_subdomain=self.subdomain_portalapi,
            path=(
                '/organisations/id/%s/numbers/shop'
                %
                self.cached_organisation_id
            ),
            data={"referenceIds": (reference_id,)},
            authorization_scheme='instance'
        )

    def filter_available_numbers(
        self, country=None, number_type=None, pattern=None
    ):
        available_numbers = self.get_available_numbers()

        if number_type and number_type.lower() not in ('voice', 'sms'):
            pass
            # TODO: exception

        if number_type:
            number_type = number_type.capitalize()
            available_numbers = tuple(
                number_pool
                for number_pool in available_numbers
                if number_pool['type'] == number_type
            )

        if country:
            country = country.upper()
            available_numbers = tuple(
                number_pool
                for number_pool in available_numbers
                if number_pool['countryId'] == country
            )

        if pattern:
            # TODO: implement this
            pass

        return available_numbers
