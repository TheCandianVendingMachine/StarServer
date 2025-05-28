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

def main():
    #print(f"Star's ID: {get_id()}")
    server = WebHandler()
    server.run()

if __name__ == '__main__':
    main()
