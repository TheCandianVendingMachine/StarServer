from settings import GLOBAL_CONFIGURATION

import atexit
import web
import threading
import signal
import hmac
import hashlib
import secrets
import json
import request
import requests
import nava
import logging

from pynput import keyboard
from web import webapi
from error import AuthError, LocalHostAuthError, AppAccessTokenError, UserAccessTokenError,\
        RefreshAppAccessTokenError, RefreshUserAccessTokenError, SubscribeError,\
        UnsubscribeError, GetSubscriptionsError, AppAccessRefreshNeeded, SlobsError,\
        DuplicateSubscription
from request import Request, ChannelRewardRedeem, StreamStop
from cheroot.server import HTTPServer
from cheroot.ssl.builtin import BuiltinSSLAdapter
from streamlabs import GetScene, GetFolder, GetItem, SetItemVisibility
from environment import ENVIRONMENT
from log import Logger

logger = logging.getLogger('wsgilog.log')

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
        nava.play('bonk.wav', async_mode=True)

class Subscription:
    def __init__(self, request):
        self.request = request
        self.subscribed = False
        self.error = None
        self.attempt = 0

    def subscribe(self):
        self.request.subscribe()
        self.thread = threading.Timer(
            5.0,
            Subscription._timeout,
            args=[self]
        ).start()

    def _timeout(self):
        if self.subscribed:
            return
        if self.attempt == 3:
            logger.critical('Did not successfully subscribe')
            return
        self.attempt = self.attempt + 1
        logger.warn(f'Subscription did not complete in time [{self.attempt}/3]')
        try:
            self.subscribe()
        except SubscribeError as e:
            logging.critical(f'Could not subscribe: {e}')
            self.error = e

class State:
    def __init__(self):
        GLOBAL_CONFIGURATION.require('bonk_id')
        GLOBAL_CONFIGURATION.require('fuck_fly_agaric_id')

        self.user_refresh_token = None
        self.hotkeys = KeyCommands()
        self.requests = {
            'stream_stop': StreamStop(
                stream_stop_path='api/stream_stop'
            ),
            'bonk': ChannelRewardRedeem(
                reward_id=GLOBAL_CONFIGURATION.get('bonk_id'),
                reward_redeem_path='api/bonk',
            ),
            'fuck_fly_agaric': ChannelRewardRedeem(
                reward_id=GLOBAL_CONFIGURATION.get('fuck_fly_agaric_id'),
                reward_redeem_path='api/fuck_fly_agaric',
            ),
        }

        self.subscriptions = { key: Subscription(self.requests[key]) for key in self.requests.keys() }

    def _stop(self):
        logger.info('shutting down...')
        self.unsubscribe()
        self.unfuck_fly_agaric()
        threading.Timer(
            3.0,
            signal.raise_signal,
            args=[signal.SIGINT]
        ).start()

    def shutdown(self):
        threading.Timer(1.0, State._stop, args=[self]).start()

    def bonk(self):
        logger.info('heads up knucklehead. bonk!!!!')
        self.hotkeys.bonk()

    def unfuck_fly_agaric(self):
        logger.info('UNFUCK fly agaric **remakes you**')
        try:
            scene = GetScene('Main Scene')
            fly_agaric = GetItem(scene.response['resourceId'], 'Fly agaric')
            explosion = GetItem(scene.response['resourceId'], 'Explosion')
            SetItemVisibility(fly_agaric.response['resourceId'], True)
            SetItemVisibility(explosion.response['resourceId'], False)
        except SlobsError as e:
            logger.error('Error trying to unexplode fly agaric: {e}')

    def fuck_fly_agaric(self):
        logger.info('FUCK fly agaric **explodes you**')
        try:
            scene = GetScene('Main Scene')
            fly_agaric = GetItem(scene.response['resourceId'], 'Fly agaric')
            explosion = GetItem(scene.response['resourceId'], 'Explosion')
            SetItemVisibility(fly_agaric.response['resourceId'], False)
            SetItemVisibility(explosion.response['resourceId'], True)
            threading.Timer(
                5.0,
                lambda explosion: SetItemVisibility(explosion, False),
                args=[explosion.response['resourceId']]
            ).start()
        except SlobsError as e:
            logger.error('Error trying to explode fly agaric: {e}')
        else:
            nava.play('boom.wav', async_mode=True)

    def _resubscribe(self, attempt):
        payload = requests.post('https://localhost/api/unsubscribe-all', verify=False)
        if payload.status_code != 200:
            raise SubscribeError(payload.response)
        logger.info('Successfully unsubscribed!')
        self.subscribe(attempt + 1)

    def subscribe(self, attempt=0):
        if attempt == 3:
            # will show '3' when erroring here
            raise SubscribeError(attempt)
        success = True
        for topic,subscription in self.subscriptions.items():
            try:
                logger.info(f'Subscribing "{topic}"')
                subscription.subscribe()
            except DuplicateSubscription as e:
                logger.warn(f'Duplicate subscription: {e}; attempting to unsubscribe')
                threading.Timer(0.3, State._resubscribe, args=[self, attempt]).start()
                return
            except SubscribeError as e:
                logger.warn(f'Failed to subscribe: {e}')
        if not success:
            raise SubscribeError(418)

    def unsubscribe(self):
        success = True
        for topic,subscription in self.requests.items():
            try:
                logger.info(f'Unsubscribing "{topic}"')
                subscription.unsubscribe()
            except UnsubscribeError as e:
                success = False
                logger.warn(f'Failed to unsubscribe: {e}')
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
            logger.warn('Could not refresh user access token, generating new one')
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
                raise RefreshAppAccessTokenError()
            token = self.get_app_access_token()
            GLOBAL_CONFIGURATION['app_access_token'] = token
            return self.get_all_subscriptions(attempt + 1)

        return response.json().get('data')

    def get_all_rewards(self, attempt=0) -> list[dict]:
        GLOBAL_CONFIGURATION.require('star_oauth')
        headers = {
            'Authorization': f'Bearer {GLOBAL_CONFIGURATION.get('star_oauth')}',
            'Client-Id': f'{GLOBAL_CONFIGURATION.get('app_id')}'
        }
        response = requests.get(
            'https://api.twitch.tv/helix/channel_points/custom_rewards',
            headers=headers,
            params={
                'broadcaster_id': GLOBAL_CONFIGURATION.get('star_id')
            }
        )
        if response.status_code == 400:
            raise GetRewardsError()
        elif response.status_code == 401:
            if attempt == 3:
                raise RefreshUserAccessTokenError()
            token = self.get_user_access_token()
            GLOBAL_CONFIGURATION['star_oauth'] = token
            return self.get_all_rewards(attempt + 1)
        response = response.json()
        return response['data']

class WebHandler:
    state = State()

    def namespace(self):
        return {
            'bonk': Endpoints.BonkRedeem,
            'fuck_fly_agaric': Endpoints.FuckFlyAgaricRedeem,
            'stop': Endpoints.Stop,
            'stream_stop': Endpoints.StreamStop,
            'app_access_token': Endpoints.AppAccessToken,
            'exists': Endpoints.Existing,
            'rewards': Endpoints.Rewards,
            'subscribe': Endpoints.Subscribe,
            'unsubscribe': Endpoints.Unsubscribe,
            'unsubscribe-all': Endpoints.UnsubscribeAll,
        }

    def urls(self):
        return (
            '/api/bonk', 'bonk',
            '/api/fuck_fly_agaric', 'fuck_fly_agaric',
            '/api/stop', 'stop',
            '/api/stream_stop', 'stream_stop',
            '/exists', 'exists',
            '/rewards', 'rewards',
            '/', 'app_access_token',
            '/api/unsubscribe-all', 'unsubscribe-all',
        )

    def __init__(self):
        for name,endpoint in Endpoints.__dict__.items():
            if '__' in name:
                continue
            endpoint.state = self.state
        self.app = WebServer(mapping=self.urls(), fvars=self.namespace())

    def _exit(self):
        logger.info('Shutting down server. Bye!!! Bye bye!!! Hope you had a good stream <3')
        try:
             self.state._stop()
        except UnsubscribeError as e:
             logger.warn(f'Failed to unsubscribe: {e}')
        GLOBAL_CONFIGURATION.write()
        logger.info('thats all folks')

    def run(self):
        if ENVIRONMENT.use_ssl():
            print('using ssl')
            logger.info('using ssl...')
            HTTPServer.ssl_adapter = BuiltinSSLAdapter(
                certificate='certs/star.pem',
                private_key='certs/star.priv'
            )
        else:
            print('ignoring ssl [LOCAL ONLY]')
            logger.info('ignoring ssl [LOCAL ONLY]')
        atexit.register(WebHandler._exit, self)
        self.app.run(port=ENVIRONMENT.port())

class WebServer(web.application):
    def run(self, port=8080, *middleware):
        func = self.wsgifunc(Logger)
        logger.info('running stars server! for doing star things! waow!')
        logger.info('-'*50)
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
            logger.warn(f'Non-local API called from abroad: {e}')
            return webapi.forbidden()
        return func(*args, **kwargs)
    return wrapper

def require_twitch(method: str):
    def verify_wrapper(func):
        assert method in WebHandler.state.requests
        def wrapper(*args, **kwargs):
            try:
                verify_twitch_webhook(WebHandler.state.requests.get(method), web.ctx.env, web.data())
            except AuthError as e:
                logger.warn(f'Attempt to call a Twitch-only method from not-Twitch: {e}')
                return webapi.forbidden()

            if 'HTTP_TWITCH_EVENTSUB_MESSAGE_TYPE' not in web.ctx.env:
                return webapi.forbidden()

            message_type = web.ctx.env.get('HTTP_TWITCH_EVENTSUB_MESSAGE_TYPE')
            if message_type == 'webhook_callback_verification':
                logger.info(f'initial challenge [{method}]')
                payload = json.loads(web.data())
                challenge = payload.get('challenge')
                WebHandler.state.subscriptions[method].subscribed = True
                return challenge
            return func(*args, **kwargs)
        return wrapper
    return verify_wrapper

class Endpoints:
    class BaseEndpoint:
        state: State

    class Existing(BaseEndpoint):
        @require_local
        def GET(self):
            try:
                subscriptions = self.state.get_all_subscriptions()
            except RefreshUserAccessTokenError:
                return '<h1>User authentication is not valid</h1>'

            html = '<h1>Subscriptions</h1>'
            html = html + '\
<form action=/api/unsubscribe-all method=POST>\
<button>Unsubscribe from all</button>\
</form>\
'
            for sub in subscriptions:
                html = html + f'<p>status={sub.get('status')}</p>'
                html = html + f'<p>type={sub.get('type')}</p>'
                html = html + f'<p>type={sub.get('condition')}</p>'
                html = html + f'<p>type={sub.get('transport')}</p>'
                html = html + f'<p>----</p>'
            return html

    class Rewards(BaseEndpoint):
        @require_local
        def GET(self):
            try:
                rewards = self.state.get_all_rewards()
            except RefreshUserAccessTokenError:
                return '<h1>User authentication is not valid</h1>'

            html = '<h1>Rewards</h1>'
            for reward in rewards:
                html = html + f'<p>title={reward.get('title')}</p>'
                html = html + f'<p>id={reward.get('id')}</p>'
                html = html + f'<p>----</p>'
            return html

    class AppAccessToken(BaseEndpoint):
        def authorize_access_tokens(self, params: dict):
            try:
                GLOBAL_CONFIGURATION['app_access_token'] = self.state.get_app_access_token()
            except AppAccessTokenError as e:
                return f'<h1>Failed to generate app access token</h1>'
            GLOBAL_CONFIGURATION.write()
            logger.info('Generated and updated app access token to configuration')

            access_code = params['code']
            try:
                GLOBAL_CONFIGURATION['star_oauth'] = self.state.get_user_access_token(access_code)
            except UserAccessTokenError as e:
                return f'<h1>Failed to generate user access token</h1>'
            GLOBAL_CONFIGURATION.write()
            logger.info('Generated and updated user access token to configuration')

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

    class StreamStop(BaseEndpoint):
        @require_twitch('stream_stop')
        def POST(self):
            logger.info('stopping due to end of stream')

            self.state.shutdown()
            return webapi.ok()

    class Stop(BaseEndpoint):
        @require_local
        def POST(self):
            self.state.shutdown()
            return webapi.ok()

    class BonkRedeem(BaseEndpoint):
        @require_twitch('bonk')
        def POST(self):
            self.state.bonk()
            return webapi.ok()

    class FuckFlyAgaricRedeem(BaseEndpoint):
        @require_twitch('fuck_fly_agaric')
        def POST(self):
            self.state.fuck_fly_agaric()
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
            logger.info(f'POST unsubscribing all')
            try:
                subscriptions = self.state.get_all_subscriptions()
            except RefreshUserAccessTokenError:
                return webapi.forbidden()

            def unsub(id, attempt=0):
                if attempt == 3:
                    raise RefreshAppAccessTokenError()

                try:
                    logger.info(f'unsubscribing from {sub.get('id')}')
                    request.unsubscribe(sub.get('id'))
                except UnsubscribeError as e:
                    logger.warn(f'failed to unsubscribe: {e}')
                except AppAccessRefreshNeeded:
                    logger.warn(f'refreshing app access token ({attempt + 1}/3)')
                    try:
                        GLOBAL_CONFIGURATION['app_access_token'] = self.state.get_app_access_token(access_code)
                    except AppAccessTokenError as e:
                        logger.error('failed to refresh: {e}')

                    unsub(id, attempt + 1)

            for sub in subscriptions:
                try:
                    unsub(sub)
                except RefreshAppAccessTokenError as e:
                    logger.error(e)

            return webapi.ok()
