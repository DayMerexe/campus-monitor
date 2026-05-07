import socket
s = socket.socket()
s.bind(('0.0.0.0', 8888))
s.listen(1)
print('等连接...')
c, addr = s.accept()
print(f'已连接: {addr}')
c.send(b'HELLO\n')
