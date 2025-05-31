from enum import Enum, auto
from settings import GLOBAL_CONFIGURATION

class Environment:
    def port(self):
        raise NotImplementedError()

    def use_ssl(self):
        raise NotImplementedError()

class Local(Environment):
    def port(self):
        return 8080

    def use_ssl(self):
        return False

class Production(Environment):
    def port(self):
        return 443

    def use_ssl(self):
        return True

if GLOBAL_CONFIGURATION.get('environment', 'local') == 'prod':
    ENVIRONMENT = Production()
else:
    ENVIRONMENT = Local()
