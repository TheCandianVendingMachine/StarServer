from wsgilog import WsgiLog

class Logger(WsgiLog):
    def __init__(self, application):
        WsgiLog.__init__(
            self,
            application,
            logformat='(%(asctime)s) %(levelname)s - %(message)s',
            tofile=True,
            tostream=False,
            toprint=True,
            file='history.log',
            interval='s',
            backups=4,
        )
