from multiprocessing import Process
from server import WebHandler
from settings import GLOBAL_CONFIGURATION
import json
import requests
GLOBAL_CONFIGURATION.require('app_id')
GLOBAL_CONFIGURATION.require('star_oauth')

def get_id() -> str:
    headers = {
        'Authorization': f'Bearer {GLOBAL_CONFIGURATION.get('star_oauth')}',
        'Client-Id': f'{GLOBAL_CONFIGURATION.get('app_id')}'
    }
    response = requests.get('https://api.twitch.tv/helix/users', headers=headers, params={'login': 'hallowedstarshroom'})
    response = response.json()
    return str(response['data'][0]['id'])

def get_rewards() -> list[str]:
    GLOBAL_CONFIGURATION.require('star_oauth')
    headers = {
        'Authorization': f'Bearer {GLOBAL_CONFIGURATION.get('star_oauth')}',
        'Client-Id': f'{GLOBAL_CONFIGURATION.get('app_id')}'
    }
    response = requests.get('https://api.twitch.tv/helix/channel_points/custom_rewards', headers=headers, params={'broadcaster_id': GLOBAL_CONFIGURATION.get('star_id')})
    response = response.json()
    return ''

def main():
    print(f"Star's ID: {get_id()}")
    print(get_rewards())
    server = WebHandler()
    server.run()

if __name__ == '__main__':
    main()
