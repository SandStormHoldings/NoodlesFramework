version_info = (0, 3, 0, 'dev')
__version__ = ".".join(map(str, version_info))

__all__ = ['WebSocketHandler']

from noodles.geventwebsocket.handler import WebSocketHandler
