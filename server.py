from settings import GLOBAL_CONFIGURATION
GLOBAL_CONFIGURATION.require('local_secret')
GLOBAL_CONFIGURATION.require('bonk_id')

import atexit
import web
import threading
import signal
import hmac
import hashlib
import secrets
import json
import requests
import nava

from pynput import keyboard
from web import webapi
from error import AuthError, LocalHostAuthError, AppAccessTokenError, UserAccessTokenError,\
        RefreshAppAccessTokenError, RefreshUserAccessTokenError, SubscribeError,\
        UnsubscribeError, GetSubscriptionsError, AppAccessRefreshNeeded
from request import Request, ChannelRewardRedeem
from cheroot.server import HTTPServer
from cheroot.ssl.builtin import BuiltinSSLAdapter

class KeyCommands:
    def __init__(self):
        self.keyboard = keyboard.Controller()

    def _stop(self, sequence: list):
        for key in sequence:
            self.keyboard.release(key)

    def _play(self, sequence: list):
        for key in sequence:
            self.keyboard.press(key)
        threading.Timer(0.01, KeyCommands._stop, [self, sequence]).start()

    def bonk(self):
        self._play([keyboard.Key.shift, 'n'])
        nava.play('bonk.wav')

class State:
    def __init__(self):
        self.user_refresh_token = None
        self.hotkeys = KeyCommands()
        self.requests = {
            'bonk': ChannelRewardRedeem(
                reward_id=GLOBAL_CONFIGURATION.get('bonk_id'),
                reward_redeem_path='api/bonk',
            )
        }

    def _stop():
        print('shutting down...')
        self.unsubscribe()
        signal.raise_signal(signal.SIGINT)

    def shutdown(self):
        threading.Timer(1.0, State._stop).start()

    def bonk(self):
        print('heads up knucklehead. bonk!!!!')
        self.hotkeys.bonk()

    def subscribe(self):
        success = True
        for topic,subscription in self.requests.items():
            try:
                print(f'Subscribing "{topic}"')
                subscription.subscribe()
            except SubscribeError as e:
                print(f'Failed to subscribe: {e}')
        if not success:
            raise SubscribeError(418)

    def unsubscribe(self):
        success = True
        for topic,subscription in self.requests.items():
            try:
                print(f'Unsubscribing "{topic}"')
                subscription.unsubscribe()
            except UnsubscribeError as e:
                success = False
                print(f'Failed to unsubscribe: {e}')
        if not success:
            raise UnsubscribeError('some subscriptions could not be done')

    def get_app_access_token(self) -> str:
        response = requests.post(
            'https://id.twitch.tv/oauth2/token',
            data={
                'client_id': GLOBAL_CONFIGURATION.get('app_id'),
                'client_secret': GLOBAL_CONFIGURATION.get('client_secret'),
                'grant_type': 'client_credentials'
            }
        )
        if response.status_code == 200:
            payload = json.loads(response.content)
            return payload.get('access_token')
        else:
            raise AppAccessTokenError()

    def get_user_access_token(self, code: str) -> str:
        try:
            return self.refresh_user_access_token()
        except RefreshUserAccessTokenError:
            print('Could not refresh user access token, generating new one')
        response = requests.post(
            'https://id.twitch.tv/oauth2/token',
            data={
                'client_id': GLOBAL_CONFIGURATION.get('app_id'),
                'client_secret': GLOBAL_CONFIGURATION.get('client_secret'),
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': 'https://localhost:443'
            }
        )
        if response.status_code == 200:
            payload = json.loads(response.content)
            self.user_refresh_token = payload.get('refresh_token')
            return payload.get('access_token')
        else:
            raise UserAccessTokenError()

    def refresh_user_access_token(self) -> str:
        if self.user_refresh_token is None:
            raise RefreshUserAccessTokenError()

        response = requests.post(
            'https://id.twitch.tv/oauth2/token',
            data={
                'client_id': GLOBAL_CONFIGURATION.get('app_id'),
                'client_secret': GLOBAL_CONFIGURATION.get('client_secret'),
                'grant_type': 'refresh_token',
                'refresh_token': self.user_refresh_token
            }
        )

        if response.status_code == 400:
            raise RefreshUserAccessTokenError()

        payload = json.loads(response.content)
        self.user_refresh_token = payload.get('refresh_token')
        return payload.get('access_token')

    def get_all_subscriptions(self, attempt=0):
        headers = {
            'Authorization': f'Bearer {GLOBAL_CONFIGURATION.get('app_access_token')}',
            'Client-Id': f'{GLOBAL_CONFIGURATION.get('app_id')}'
        }
        response = requests.get(
            'https://api.twitch.tv/helix/eventsub/subscriptions',
            headers=headers
        )
        if response.status_code == 400:
            raise GetSubscriptionsError()
        elif response.status_code == 401:
            if attempt == 3:
                raise RefreshUserAccessTokenError()
            token = self.get_app_access_token()
            GLOBAL_CONFIGURATION['app_access_token'] = token
            return self.get_all_subscriptions(attempt + 1)

        return response.json().get('data')

class WebHandler:
    state = State()

    def namespace(self):
        return {
            'bonk': Endpoints.BonkRedeem,
            'stop': Endpoints.Stop,
            'app_access_token': Endpoints.AppAccessToken,
            'exists': Endpoints.Existing,
            'subscribe': Endpoints.Subscribe,
            'unsubscribe': Endpoints.Unsubscribe,
            'unsubscribe-all': Endpoints.UnsubscribeAll,
        }

    def urls(self):
        return (
            '/api/bonk', 'bonk',
            '/local/stop', 'stop',
            '/exists', 'exists',
            '/', 'app_access_token',
            '/unsubscribe-all', 'unsubscribe-all',
        )

    def __init__(self):
        for name,endpoint in Endpoints.__dict__.items():
            if '__' in name:
                continue
            endpoint.state = self.state
        self.app = WebServer(mapping=self.urls(), fvars=self.namespace())
        print(self.app.ctx.environ)

    def _exit(self):
        print('Shutting down server. Bye!!! Bye bye!!! Hope you had a good stream <3')
        try:
             self.state.unsubscribe()
        except UnsubscribeError as e:
             print(f'Failed to unsubscribe: {e}')
        GLOBAL_CONFIGURATION.write()
        print('thats all folks')

    def run(self):
        print('running stars server! for doing star things! waow!')
        print('-'*50)
        HTTPServer.ssl_adapter = BuiltinSSLAdapter(
            certificate='certs/star.pem',
            private_key='certs/star.priv'
        )
        atexit.register(WebHandler._exit, self)
        self.app.run(port=443)

class WebServer(web.application):
    def run(self, port=8080, *middleware):
        func = self.wsgifunc(*middleware)
        return web.httpserver.runsimple(func, ('0.0.0.0', port))

def verify_local(ctx: dict):
    valid_local_prefix = (
        '0.',
        '10.',
        '127.',
        '172.16.',
        '192.0.0.',
        '192.168.',
    )
    ip = ctx.get('ip', '255.255.255.255')
    if not any([ip.startswith(prefix) for prefix in valid_local_prefix]):
        raise LocalHostAuthError(ip)

def verify_twitch_webhook(request: Request, env: dict, body: str):
    message_id = env.get('HTTP_TWITCH_EVENTSUB_MESSAGE_ID')
    timestamp = env.get('HTTP_TWITCH_EVENTSUB_MESSAGE_TIMESTAMP')
    signature = env.get('HTTP_TWITCH_EVENTSUB_MESSAGE_SIGNATURE')
    if message_id is None or timestamp is None or signature is None:
        raise AuthError()

    secret = request.transport.secret
    message = f'{message_id}{timestamp}{body.decode('utf-8')}'
    computed_signature = f'sha256={hmac.new(
        bytes(secret, 'utf-8'),
        msg=bytes(message, 'utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()}'

    if not secrets.compare_digest(computed_signature, signature):
        raise AuthError()

def require_local(func):
    def wrapper(*args, **kwargs):
        try:
            verify_local(web.ctx)
        except LocalHostAuthError as e:
            print(f'Non-local API called from abroad: {e}')
            return webapi.forbidden()
        return func(*args, **kwargs)
    return wrapper

def require_twitch(request_member: str):
    def verify_wrapper(func):
        assert request_member in WebHandler.state.requests
        def wrapper(*args, **kwargs):
            try:
                verify_twitch_webhook(WebHandler.state.requests.get(request), web.ctx.env, web.data())
            except AuthError as e:
                print(f'Attempt to call a Twitch-only method from not-Twitch: {e}')
                return webapi.forbidden()
            func(*args, **kwags)
        return wrapper
    return verify_wrapper

class Endpoints:
    class BaseEndpoint:
        state: State

    class Existing(BaseEndpoint):
        def GET(self):
            try:
                subscriptions = self.state.get_all_subscriptions()
            except RefreshUserAccessTokenError:
                return '<h1>User authentication is not valid</h1>'

            html = '<h1>Subscriptions</h1>'
            html = html + '\
<form action=/unsubscribe-all method=POST>\
<button>Unsubscribe from all</button>\
</form>\
'
            for sub in subscriptions:
                html = html + f'<p>status={sub.get('status')}</p>'
                html = html + f'<p>type={sub.get('type')}</p>'
                html = html + f'<p>----</p>'
            return html

    class AppAccessToken(BaseEndpoint):
        def authorize_access_tokens(self, params: dict):
            try:
                GLOBAL_CONFIGURATION['app_access_token'] = self.state.get_app_access_token()
            except AppAccessTokenError as e:
                return f'<h1>Failed to generate app access token</h1>'
            GLOBAL_CONFIGURATION.write()
            print('Generated and updated app access token to configuration')

            access_code = params['code']
            try:
                GLOBAL_CONFIGURATION['star_oauth'] = self.state.get_user_access_token(access_code)
            except UserAccessTokenError as e:
                return f'<h1>Failed to generate user access token</h1>'
            GLOBAL_CONFIGURATION.write()
            print('Generated and updated user access token to configuration')

            try:
                self.state.subscribe()
            except SubscribeError as e:
                return f'<h1>Failed to subscribe to some topics</h1>'

            return f'\
<h1>Successfully authorized app and user access token</h1>\
<p>You can close this window</p>\
'

        def GET(self):
            params = web.input()
            if 'error' in params:
                return f'<h1>User denied authorization</h1>'

            if 'code' in params:
                return self.authorize_access_tokens(params)

            return f'<h1>Homepage</h1>'

    class Stop(BaseEndpoint):
        @require_local
        def POST(self):
            self.state.shutdown(secret=data.secret)
            return webapi.ok()

    class BonkRedeem(BaseEndpoint):
        @require_twitch
        def POST(self):
            if 'HTTP_TWITCH_EVENTSUB_MESSAGE_TYPE' not in web.ctx.env:
                return webapi.forbidden()

            message_type = web.ctx.env.get('HTTP_TWITCH_EVENTSUB_MESSAGE_TYPE')
            if message_type == 'webhook_callback_verification':
                print('initial challenge [bonk]')
                payload = json.loads(web.data())
                challenge = payload.get('challenge')
                return challenge
            self.state.bonk()
            return webapi.ok()

    class Subscribe(BaseEndpoint):
        @require_local
        def POST(self):
            self.state.subscribe()
            return webapi.ok()

    class Unsubscribe(BaseEndpoint):
        @require_local
        def POST(self):
            self.state.unsubscribe()
            return webapi.ok()

    class UnsubscribeAll(BaseEndpoint):
        @require_local
        def POST(self):
            try:
                subscriptions = self.state.get_all_subscriptions()
            except RefreshUserAccessTokenError:
                return webapi.forbidden()

            def unsub(id, attempt=0):
                if attempt == 3:
                    raise RefreshAppAccessTokenError()

                try:
                    print(f'unsubscribing from {sub.get('id')}')
                    request.unsubscribe(sub.get('id'))
                except UnsubscribeError as e:
                    print(f'failed to unsubscribe: {e}')
                except AppAccessRefreshNeeded:
                    print(f'refreshing app access token ({attempt + 1}/3)')
                    try:
                        GLOBAL_CONFIGURATION['app_access_token'] = self.state.get_app_access_token(access_code)
                    except AppAccessTokenError as e:
                        print('failed to refresh: {e}')

                    unsub(id, attempt + 1)

            for sub in subscriptions:
                try:
                    unsub(sub)
                except RefreshAppAccessTokenError as e:
                    print(e)

            return webapi.ok()
