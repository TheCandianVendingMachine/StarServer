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

class SubscribeError(Exception):
    def __init__(self, status: int):
        super().__init__(f'Failed to subscribe to an event: status {status}')

class UnsubscribeError(Exception):
    def __init__(self, reason: str):
        super().__init__(f'Failed to unsubscribe from an event: {reason}')

class NotSubscribedError(UnsubscribeError):
    def __init__(self):
        super().__init__(f'Not subscribed')

class NoConfigLoadedError(Exception):
    def __init__(self):
        super().__init__(f'Attempting to write a configuration file when none available')

class AppAccessTokenError(Exception):
    def __init__(self):
        super().__init__(f'Failed to generate app access token')

class UserAccessTokenError(Exception):
    def __init__(self):
        super().__init__(f'Failed to generate user access token')

class RefreshUserAccessTokenError(Exception):
    def __init__(self):
        super().__init__(f'Failed to refresh user access token')
