from error import DuplicateConfigKeyException, ConfigurationKeyNotPresent

GLOBAL_CONFIGURATION = None

class Configuration(dict):
    def require(self, key: str):
        if key not in self:
            raise ConfigurationKeyNotPresent(key=key)

if GLOBAL_CONFIGURATION is None:
    GLOBAL_CONFIGURATION = Configuration()
    with open('conf.txt', 'r') as file:
        for line in file:
            line = line.strip()
            if len(line) == 0:
                continue
            if line[0] == '#':
                continue

            if '=' in line:
                key, value = (s.strip() for s in line.split('='))
                if key in GLOBAL_CONFIGURATION:
                    raise DuplicateConfigKeyException(key=key)
                GLOBAL_CONFIGURATION[key] = value
            else:
                if line in GLOBAL_CONFIGURATION:
                    raise DuplicateConfigKeyException(key=line)
                GLOBAL_CONFIGURATION[line] = ''
