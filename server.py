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

from web import webapi
from error import AuthError, LocalHostAuthError
from request import Request, ChannelRewardRedeem
from cheroot.server import HTTPServer
from cheroot.ssl.builtin import BuiltinSSLAdapter

class State:
    def __init__(self):
        self.requests = {
            'bonk': ChannelRewardRedeem(
                reward_id=GLOBAL_CONFIGURATION.get('bonk_id'),
                reward_redeem_path='api/bonk',
            )
        }
        print(self.requests['bonk'].transport.secret)

    def _stop():
        print('shutting down...')
        signal.raise_signal(signal.SIGINT)

    def shutdown(self, secret: str):
        if secret != GLOBAL_CONFIGURATION.get('local_secret'):
            raise LocalHostAuthError(secret=secret)
        threading.Timer(1.0, State._stop).start()

    def bonk(self):
        print('heads up knucklehead. bonk!!!!')

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

    class Auth(BaseEndpoint):
        def GET(self):
            params = web.input()
            response = requests.post(
                'https://id.twitch.tv/oauth2/token',
                data={
                    'client_id': GLOBAL_CONFIGURATION.get('app_id'),
                    'client_secret': GLOBAL_CONFIGURATION.get('client_secret'),
                    'grant_type': 'client_credentials'
                }
            )
            payload = json.loads(response.content)
            token = payload.get('access_token')
            print(token)
            return f'<h1>Success!</h1>'

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

class WebHandler:
    def namespace(self):
        return {
            'bonk': Endpoints.BonkRedeem,
            'stop': Endpoints.Stop,
            'auth': Endpoints.Auth,
            'exists': Endpoints.Existing
        }

    def urls(self):
        return (
            '/api/bonk', 'bonk',
            '/local/stop', 'stop',
            '/exists', 'exists',
            '/', 'auth',
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
