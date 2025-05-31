from error import PipeError, PipeNotFound, PipeBroken
import importlib

class Pipe:
    def connect(self, pipe):
        raise NotImplementedError()

    def talk(self, message):
        raise NotImplementedError()

    def listen(self):
        raise NotImplementedError()

class EmptyPipe(Pipe):
    def connect(self, pipe):
        pass

    def talk(self, message):
        pass

    def listen(self):
        return None

if importlib.util.find_spec('win32pipe') is not None:
    import win32pipe
    import win32file
    import win32api
    import pywintypes

    class WindowsPipe(Pipe):
        def __init__(self):
            self.pipe = None

        def __del__(self):
            if self.pipe is not None:
                self.pipe.close()

        def connect(self, pipe):
            try:
                self.pipe = win32file.CreateFile(
                    rf'\\.\pipe\{pipe}',
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
                    raise PipeError(reason)
            except pywintypes.error as e:
                self.pipe.close()
                self.pipe = None

                if e.args[0] == 2:
                    raise PipeNotFound()
                elif e.args[0] == 209:
                    raise PipeBroken()
                raise PipeError(f'unhandled error: {e}')
            except PipeError as e:
                self.pipe.close()
                self.pipe = None
                raise e

    def talk(self, message):
        try:
            win32file.WriteFile(self.pipe, message)
        except pywintypes.error as e:
            self.pipe.close()
            self.pipe = None

            if e.args[0] == 2:
                raise PipeNotFound()
            elif e.args[0] == 209:
                raise PipeBroken()
            raise PipeError(f'unhandled error: {e}')
        except PipeError as e:
            self.pipe.close()
            self.pipe = None
            raise e

    def listen(self):
        try:
            result, response = win32file.ReadFile(self.pipe, 128 * 1024)
            return response
        except pywintypes.error as e:
            self.pipe.close()
            self.pipe = None

            if e.args[0] == 2:
                raise PipeNotFound()
            elif e.args[0] == 209:
                raise PipeBroken()
            raise PipeError(f'unhandled error: {e}')
        except PipeError as e:
            self.pipe.close()
            self.pipe = None
            raise e
else:
    class WindowsPipe(EmptyPipe):
        pass
