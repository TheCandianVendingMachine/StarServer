from error import SlobsError, SlobsPipeBroken, SlobsNoPipePresent, SlobsNoResponse
import uuid
import win32pipe
import win32file
import win32api

class Control:
    def __init__(self):
        self.response = {}
        try:
            pipe = win32file.CreateFile(
                r'\\.\pipe\slobs',
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )
            res = win32pipe.SetNamedPipeHandleState(
                pipe,
                win32pipe.PIPE_READMODE_MESSAGE,
                None,
                None
            )
            if res == 0:
                reason = win32api.GetLastError()
                raise SlobsError(reason)

            id = str(uuid.uuid4())
            message = str.encode({
                'jsonrpc': '2.0',
                'id': id,
                'method': self.method(),
                'params': self.parameters()
            })
            win32file.WriteFile(pipe, message)
            for i in range(0, 16):
                result, response = win32file.ReadFile(pipe, 128 * 1024)
                self.response = json.loads(response.decode('utf-8'))
                if self.response['id'] == id:
                    return
            raise SlobsNoResponse()
        except pywintypes.error as e:
            if e.args[0] == 2:
                raise SlobsNoPipePresent()
            elif e.args[0] == 209:
                raise SlobsPipeBroken()

    def method(self) -> str:
        raise NotImplementedError()

    def parameters(self) -> dict:
        raise NotImplementedError()

class GetScene(Control):
    def __init__(self, scene: str):
        self.scene = scene
        super().__init__()

    def method(self) -> str:
        return 'getScene'

    def parameters(self) -> dict:
        return {
            'resource': 'ScenesService',
            'args': [self.scene]
        }

class GetFolder(Control):
    def __init__(self, scene_resource: str, folder: str):
        self.scene_resource = scene_resource
        self.folder = folder
        super().__init__()

    def method(self) -> str:
        return 'getFolder'

    def parameters(self) -> dict:
        return {
            'resource': self.scene_resource,
            'args': [self.folder]
        }

class GetItem(Control):
    def __init__(self, scene_resource: str, item: str):
        self.scene_resource = scene_resource
        self.item = item
        super().__init__()

    def method(self) -> str:
        return 'getItem'

    def parameters(self) -> dict:
        return {
            'resource': self.scene_resource,
            'args': [self.item]
        }

class SetItemVisibility(Control):
    def __init__(self, item_resource: str, visible: bool):
        self.item_resource = item_resource
        self.visible = visible
        super().__init__()

    def method(self) -> str:
        return 'setVisibility'

    def parameters(self) -> dict:
        return {
            'resource': self.item_resource,
            'args': [self.visible]
        }
