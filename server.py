from settings import GLOBAL_CONFIGURATION
GLOBAL_CONFIGURATION.require('local_secret')
GLOBAL_CONFIGURATION.require('bonk_id')

import web
import threading
import signal
import hmac
import hashlib
import secrets
import json
import requests
import keyboard

from web import webapi
from error import AuthError, LocalHostAuthError, AppAccessTokenError, UserAccessTokenError, RefreshUserAccessTokenError, SubscribeError
from request import Request, ChannelRewardRedeem
from cheroot.server import HTTPServer
from cheroot.ssl.builtin import BuiltinSSLAdapter

class State:
    def __init__(self):
        self.user_refresh_token = None
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

    def shutdown(self, secret: str):
        if secret != GLOBAL_CONFIGURATION.get('local_secret'):
            raise LocalHostAuthError(secret=secret)
        threading.Timer(1.0, State._stop).start()

    def bonk(self):
        print('heads up knucklehead. bonk!!!!')
        keyboard.press_and_release('shift+n')

    def subscribe(self):
        for topic,subscription in self.requests.items():
            try:
                print(f'Subscribing "{topic}"')
                subscription.subscribe()
            except SubscribeError as e:
                print(f'Failed to subscribe: {e}')

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

class WebServer(web.application):
    def run(self, port=8080, *middleware):
        func = self.wsgifunc(*middleware)
        return web.httpserver.runsimple(func, ('0.0.0.0', port))

class Endpoints:
    class BaseEndpoint:
        state: State

        def verify(self, request: Request, env: dict, body: str):
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

    class Existing(BaseEndpoint):
        def GET(self):
            headers = {
                'Authorization': f'Bearer {GLOBAL_CONFIGURATION.get('app_access_token')}',
                'Client-Id': f'{GLOBAL_CONFIGURATION.get('app_id')}'
            }
            response = requests.get(
                'https://api.twitch.tv/helix/eventsub/subscriptions',
                headers=headers
            )
            if response.status_code != 200:
                return '<h1>Error, could not fetch data</h1>'
            html = f'<h1>Subscriptions</h1>'
            for sub in response.json().get('data'):
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
        def POST(self):
            data = web.input(secret='')
            try:
                self.state.shutdown(secret=data.secret)
            except LocalHostAuthError:
                return webapi.forbidden()
            else:
                return webapi.ok()

    class BonkRedeem(BaseEndpoint):
        def POST(self):
            try:
                self.verify(self.state.requests.get('bonk'), web.ctx.env, web.data())
            except AuthError as e:
                print(e)
                return webapi.forbidden()

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
        def POST(self):
            self.state.subscribe()
            return webapi.ok()

class WebHandler:
    def namespace(self):
        return {
            'bonk': Endpoints.BonkRedeem,
            'stop': Endpoints.Stop,
            'app_access_token': Endpoints.AppAccessToken,
            'exists': Endpoints.Existing,
            'subscribe': Endpoints.Subscribe,
        }

    def urls(self):
        return (
            '/api/bonk', 'bonk',
            '/local/stop', 'stop',
            '/exists', 'exists',
            '/', 'app_access_token',
        )

    def __init__(self):
        self.state = State()
        for name,endpoint in Endpoints.__dict__.items():
            if '__' in name:
                continue
            endpoint.state = self.state
        self.app = WebServer(mapping=self.urls(), fvars=self.namespace())

    def run(self):
        print('running twitch listen server')
        print('-'*50)
        HTTPServer.ssl_adapter = BuiltinSSLAdapter(
            certificate='certs/star.pem',
            private_key='certs/star.priv'
        )
        self.app.run(port=443)
