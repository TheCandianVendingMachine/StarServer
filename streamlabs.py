from error import SlobsError, SlobsPipeBroken, SlobsNoPipePresent, SlobsNoResponse
from rpc import WindowsPipe
import uuid
import json

class Control:
    def __init__(self):
        self.response = {}
        pipe = WindowsPipe()
        pipe.connect('slobs')

        id = str(uuid.uuid4())
        message = json.dumps({
            'jsonrpc': '2.0',
            'id': id,
            'method': self.method(),
            'params': self.parameters()
        }).encode()

        pipe.talk(message)
        for i in range(0, 16):
            response = pipe.listen()
            self.response = json.loads(response.decode('utf-8'))
            if self.response['id'] == id:
                self.response = self.response['result']
                return
        raise SlobsNoResponse()

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
