from multiprocessing import Process
from server import WebHandler

def main():
    server = WebHandler()
    server.run()

if __name__ == '__main__':
    main()
