"""
模拟程序
"""

from socket import socket, AF_INET, SOCK_DGRAM

if __name__ == '__main__':
    s = socket(AF_INET, SOCK_DGRAM)
    s.sendto(b'', ('localhost', 20000))


