from urllib.parse import urljoin
from enum import StrEnum
from settings import GLOBAL_CONFIGURATION
from base64 import b64encode
from error import SubscribeError, UnsubscribeError, NotSubscribedError, AppAccessRefreshNeeded
import os
import json
import requests

GLOBAL_CONFIGURATION.require('url')
GLOBAL_CONFIGURATION.require('secret_length')
GLOBAL_CONFIGURATION.require('star_id')
GLOBAL_CONFIGURATION.require('app_id')
GLOBAL_CONFIGURATION.require('app_access_token')

def unsubscribe(id: str):
    headers = {
        'Authorization': f'Bearer {GLOBAL_CONFIGURATION.get('app_access_token')}',
        'Client-Id': f'{GLOBAL_CONFIGURATION.get('app_id')}',
    }
    response = requests.delete(
        'https://api.twitch.tv/helix/eventsub/subscriptions',
        headers=headers,
        data={ 'id': self.id }
    )

    if response.status_code == 400:
        raise UnsubscribeError('Didnt pass in valid ID')
    elif response.status_code == 401:
        raise AppAccessRefreshNeeded()
    elif response.status_code == 404:
        raise UnsubscribeError('Subscription does not exist')

class Subscription(StrEnum):
    CHANNEL_REWARD_REDEEM = 'channel.channel_points_custom_reward_redemption.add'

class Transport:
    def as_dict(self) -> dict:
        raise NotImplementedError()

class Webhook(Transport):
    def __init__(self, path: str):
        self.path = urljoin(GLOBAL_CONFIGURATION.get('url'), path)
        self.secret = b64encode(os.urandom(int(GLOBAL_CONFIGURATION.get('secret_length')))).decode('utf-8')

    def as_dict(self) -> dict:
        return {
            'method': 'webhook',
            'callback': self.path,
            'secret': self.secret
        }

class Websocket(Transport):
    def __init__(self, session: str):
        self.session_id = session

class Condition:
    def __init__(self):
        self.broadcaster_user_id = GLOBAL_CONFIGURATION.get('star_id')

    def as_dict(self) -> dict:
        raise NotImplementedError()

class ChannelRewardCondition(Condition):
    def __init__(self, reward_id: str):
        self.reward_id = reward_id
        super().__init__()

    def as_dict(self) -> dict:
        return {
            'broadcaster_user_id': self.broadcaster_user_id,
            'reward_id': self.reward_id
        }

class Request:
    def __init__(
        self,
        subscription: Subscription,
        version: str,
        condition: Condition,
        transport: Transport
    ):
        self.type = subscription
        self.version = version
        self.condition = condition
        self.transport = transport
        self.id = None

    def subscribe(self):
        headers = {
            'Authorization': f'Bearer {GLOBAL_CONFIGURATION.get('app_access_token')}',
            'Client-Id': f'{GLOBAL_CONFIGURATION.get('app_id')}',
            'Content-Type': 'application/json'
        }
        body = json.dumps(self.as_dict())
        response = requests.post(
            'https://api.twitch.tv/helix/eventsub/subscriptions',
            headers=headers,
            data=body
        )
        if response.status_code != 200:
            raise SubscribeError(response.status_code)

        info = response.content['data'][0]
        self.id = info['id']

    def unsubscribe(self):
        if self.id is None:
            raise NotSubscribedError()
        unsubscribe(self.id)

    def as_dict(self) -> dict:
        return {
            'type': str(self.type),
            'version': self.version,
            'condition': self.condition.as_dict(),
            'transport': self.transport.as_dict()
        }

class ChannelRewardRedeem(Request):
    def __init__(self, reward_id: str, reward_redeem_path: str):
        super().__init__(
            subscription=Subscription.CHANNEL_REWARD_REDEEM,
            version='1',
            condition=ChannelRewardCondition(reward_id),
            transport=Webhook(path=reward_redeem_path)
        )
