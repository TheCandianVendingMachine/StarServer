from settings import GLOBAL_CONFIGURATION
GLOBAL_CONFIGURATION.require('local_secret')

import sys
import json
import web
import threading
import signal
from web import webapi

from error import AuthError, LocalHostAuthError

class State:
    def _stop():
        print('shutting down...')
        signal.raise_signal(signal.SIGINT)

    def shutdown(self, secret: str):
        if secret != GLOBAL_CONFIGURATION.get('local_secret'):
            raise LocalHostAuthError(secret=secret)
        threading.Timer(1.0, State._stop).start()

    def bonk(self):
        pass


class WebServer(web.application):
    def run(self, port=8080, *middleware):
        func = self.wsgifunc(*middleware)
        return web.httpserver.runsimple(func, ('0.0.0.0', port))

class Endpoints:
    class BaseEndpoint:
        state: State

    class Stop(BaseEndpoint):
        def POST(self):
            data = web.input(secret='')
            try:
                self.state.shutdown(secret=data.secret)
            except LocalHostAuthError:
                return webapi.unauthorized()
            else:
                return webapi.ok()

    class BonkRedeem(BaseEndpoint):
        def POST(self):
            data = json.loads(web.data())
            server_info = self.state.reward_redeem(requester=data.requester, server_type=ServerType(data.server_type))
            if is_err(server_info):
                return webapi.internalerror(message=str(server_info.unwrap_err()))
            server_json = json.dumps(server_info.unwrap().dict())
            return server_json

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
