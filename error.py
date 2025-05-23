class DuplicateConfigKeyException(Exception):
    def __init__(self, key: str):
        super().__init__(f'Configuration file has a duplicate key: "{key}".')

class ConfigurationKeyNotPresent(Exception):
    def __init__(self, key: str):
        super().__init__(f'Key "{key}" is not present in configuration, but is required.')

class AuthError(Exception):
    def __init__(self):
        super().__init__(f'Someone attempted to call a API with a bad Twitch secret')

class LocalHostAuthError(Exception):
    def __init__(self, secret: str):
        super().__init__(f'Someone attempted to call a local API with a bad secret: "{secret}"')
