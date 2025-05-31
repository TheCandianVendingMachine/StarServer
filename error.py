class DuplicateConfigKeyException(Exception):
    def __init__(self, key: str):
        super().__init__(f'Configuration file has a duplicate key: "{key}".')

class ConfigurationKeyNotPresent(Exception):
    def __init__(self, key: str):
        super().__init__(f'Key "{key}" is not present in configuration, but is required.')

class AuthError(Exception):
    def __init__(self):
        super().__init__(f'Someone attempted to call a API with a bad Twitch secret')

class UserAccessRefreshNeeded(Exception):
    def __init__(self):
        super().__init__(f'User access token expired')

class AppAccessRefreshNeeded(Exception):
    def __init__(self):
        super().__init__(f'App access token expired')

class LocalHostAuthError(Exception):
    def __init__(self, ip: str):
        super().__init__(f'Someone attempted to call a local API from a foreign (non-local) IP: "{ip}"')

class SubscribeError(Exception):
    def __init__(self, status: int):
        super().__init__(f'Failed to subscribe to an event: status {status}')

class DuplicateSubscription(SubscribeError):
    def __init__(self, status: int):
        super().__init__(status)

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

class RefreshAppAccessTokenError(Exception):
    def __init__(self):
        super().__init__(f'Failed to refresh app access token')

class GetSubscriptionsError(Exception):
    def __init__(self):
        super().__init__(f'Failed to get subscriptions')

class GetRewardsError(Exception):
    def __init__(self):
        super().__init__(f'Failed to get rewards')

class SlobsError(Exception):
    def __init__(self, reason: str):
        super().__init__(f'Failed to communicate with pipe. Reason: {reason}')

class SlobsPipeBroken(SlobsError):
    def __init__(self):
        super().__init__('pipe broken')

class SlobsNoPipePresent(SlobsError):
    def __init__(self):
        super().__init__('no pipe found')

class SlobsNoResponse(SlobsError):
    def __init__(self):
        super().__init__('no response from pipe')

class PipeError(Exception):
    def __init__(self, message: str):
        super().__init__(f'An error with the pipe occured: {message}')

class PipeNotFound(PipeError):
    def __init__(self):
        super().__init__('no pipe found')

class PipeBroken(PipeError):
    def __init__(self):
        super().__init__('pipe broken')

class JsonRpcError(Exception):
    def __init__(self, message: str):
        super().__init__(f'An RPC error occured: {message}')

class JsonRpcParseError(JsonRpcError):
    def __init__(self):
        super().__init__('Invalid JSON recieved by the server')

class JsonRpcInvalidRequest(JsonRpcError):
    def __init__(self):
        super().__init__('Request object not valid')

class JsonRpcMethodNotFound(JsonRpcError):
    def __init__(self, method: str):
        super().__init__(f'Trying to call method which does not exist: "{method}"')

class JsonRpcInvalidParams(JsonRpcError):
    def __init__(self):
        super().__init__(f'Invalid parameters passed to method')

class JsonRpcInternalError(JsonRpcError):
    def __init__(self):
        super().__init__(f'Internal RPC error')

class JsonRpcServerError(JsonRpcError):
    def __init__(self):
        super().__init__(f'Server Error')
