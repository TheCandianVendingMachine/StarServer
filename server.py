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

from web import webapi
from error import AuthError, LocalHostAuthError
from request import Request, ChannelRewardRedeem

class State:
    def __init__(self):
        self.requests = {
            'bonk': ChannelRewardRedeem(
                reward_id=GLOBAL_CONFIGURATION.get('bonk_id'),
                reward_redeem_path='api/bonk',
            )
        }

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
            message_id = env.get('Twitch-EventSub-Message-Id')
            timestamp = env.get('Twitch-EventSub-Message-Timestamp')
            signature = env.get('Twitch-EventSub-Message-Signature')

            if message_id is None or timestamp is None or signature is None:
                raise AuthError()

            secret = request.transport.secret
            message = f'{message_id}{timestamp}{body}'

            computed_signature = hmac.new(
                bytes(secret, 'utf-8'),
                msg=bytes(message, 'utf-8'),
                digestmod=hashlib.sha256
            ).hexdigest()

            if not secrets.compare_digest(computed_signature, signature):
                raise AuthError()


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

            self.state.bonk()
            return webapi.ok()

class WebHandler:
    def namespace(self):
        return {
            'bonk': Endpoints.BonkRedeem,
            'stop': Endpoints.Stop,
        }

    def urls(self):
        return (
            '/api/bonk', 'bonk',
            '/local/stop', 'stop',
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
        self.app.run(port=443)
