from error import SlobsError, SlobsPipeBroken, SlobsNoPipePresent, SlobsNoResponse,\
        JsonRpcInternalError, JsonRpcInvalidParams, JsonRpcInvalidRequest,\
        JsonRpcMethodNotFound, JsonRpcParseError, JsonRpcServerError, JsonRpcError
import uuid
import win32pipe
import win32file
import win32api
import pywintypes
import json

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
                win32pipe.PIPE_READMODE_BYTE,
                None,
                None
            )
            if res == 0:
                reason = win32api.GetLastError()
                raise SlobsError(reason)

            id = str(uuid.uuid4())
            message = json.dumps({
                'jsonrpc': '2.0',
                'id': id,
                'method': self.method(),
                'params': self.parameters()
            }).encode()
            win32file.WriteFile(pipe, message)
            for i in range(0, 16):
                result, response = win32file.ReadFile(pipe, 128 * 1024)
                self.response = json.loads(response.decode('utf-8'))
                if self.response['id'] == id:
                    if 'error' in self.response:
                        error_no = int(self.response['error'])
                        if error_no == -32700:
                            raise JsonRpcParseError()
                        elif error_no == -32600:
                            raise JsonRpcInvalidRequest()
                        elif error_no == -32601:
                            raise JsonRpcMethodNotFound(self.method())
                        elif error_no == -32602:
                            raise JsonRpcInvalidParams()
                        elif error_no == -32603:
                            raise JsonRpcInternalError()
                        elif error_no <= -32000 and error_no >= -32099:
                            raise JsonRpcServerError()
                        else:
                            JsonRpcError(f'error code {error_no}')
                    else:
                        self.response = self.response['result']
                    return
            raise SlobsNoResponse()
        except pywintypes.error as e:
            if e.args[0] == 2:
                raise SlobsNoPipePresent()
            elif e.args[0] == 209:
                raise SlobsPipeBroken()
            raise SlobsError(f'unhandled error: {e}')
        finally:
            pipe.close()

    def method(self) -> str:
        raise NotImplementedError()

    def parameters(self) -> dict:
        raise NotImplementedError()

class GetScenes(Control):
    def __init__(self):
        super().__init__()

    def method(self) -> str:
        return 'getScenes'

    def parameters(self) -> dict:
        return {
            'resource': 'ScenesService'
        }

class GetScene(Control):
    def __init__(self, scene_name: str):
        all_scenes = GetScenes().response
        scene_id = ''
        for scene in all_scenes:
            if scene['name'] == scene_name:
                scene_id = scene['id']
        self.scene = scene_id
        super().__init__()

    def method(self) -> str:
        return 'getScene'

    def parameters(self) -> dict:
        return {
            'resource': 'ScenesService',
            'args': [self.scene]
        }

class GetFolders(Control):
    def __init__(self, scene_resource: str):
        self.scene_resource = scene_resource
        super().__init__()

    def method(self) -> str:
        return 'getFolders'

    def parameters(self) -> dict:
        return {
            'resource': self.scene_resource,
        }

class GetFolder(Control):
    def __init__(self, scene_resource: str, folder_name: str):
        self.scene_resource = scene_resource
        all_folders = GetFolders(scene_resource).response
        folder_id = ''
        for folder in all_folders:
            if folder['name'] == folder_name:
                folder_id = folder['id']
        self.folder = folder_id
        super().__init__()

    def method(self) -> str:
        return 'getFolder'

    def parameters(self) -> dict:
        return {
            'resource': self.scene_resource,
            'args': [self.folder]
        }

class GetItems(Control):
    def __init__(self, resource: str):
        self.resource = resource
        super().__init__()

    def method(self) -> str:
        return 'getItems'

    def parameters(self) -> dict:
        return {
            'resource': self.resource,
        }

class GetItem(Control):
    def __init__(self, scene_resource: str, item_name: str):
        self.scene_resource = scene_resource
        all_items = GetItems(scene_resource).response
        item_id = ''
        for item in all_items:
            if item['name'] == item_name:
                item_id = item['sceneItemId']
        self.item = item_id
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
