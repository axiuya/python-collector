import time
from socketserver import UDPServer, BaseRequestHandler


class CollectorHandler(BaseRequestHandler):
    """处理采集器的消息"""

    def __init__(self):
        pass

    def handle(self):
        print('Got connection from', self.client_address)
        # Get message and client socket
        msg, sock = self.request
        print('msg:', msg)
        resp = time.ctime()
        sock.sendto(resp.encode('ascii'), self.client_address)


if __name__ == '__main__':
    serv = UDPServer(('', 62014), CollectorHandler)
    serv.serve_forever()
