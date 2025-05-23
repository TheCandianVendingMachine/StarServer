class DuplicateConfigKeyException(Exception):
    def __init__(self, key: str):
        super().__init__(f'Configuration file has a duplicate key: "{key}".')

class ConfigurationKeyNotPresent(Exception):
    def __init__(self, key: str):
        super().__init__(f'Key "{key}" is not present in configuration, but is required.')
