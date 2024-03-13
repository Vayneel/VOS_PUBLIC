import socket
import os
import datetime
import threading
import json

with open('data/server_settings.json') as settings_file:
    settings = json.load(settings_file)


def create_filename() -> str:
    """
    Create the filename with date
    :return: string with filename
    """
    return '[1]_' + datetime.datetime.now().strftime('%Y-%m-%d_%H+%M+%S+%f') + '.zip'


def gather_data(cl_connection: socket.socket) -> bytes:
    """
    Gather data (zip file) by slices
    :param cl_connection: connection to the server or the client
    :return: packet of bytes
    """
    file_size = int.from_bytes(cl_connection.recv(16), 'big')
    packet = b""

    while len(packet) < file_size:
        if file_size - len(packet) > 4096:
            buffer = cl_connection.recv(4096)
        else:
            buffer = cl_connection.recv(file_size - len(packet))

        if not buffer:
            raise Exception("Incomplete file received")

        packet += buffer

    return packet


def server_uploading(cl_connection: socket.socket, username: str) -> None:
    """
    Server part of the upload process
    :param cl_connection: connection to client
    :param username: name of current user
    :return: None
    """
    print('Gathering client\'s data...', end='')
    user_storage = os.path.join(settings['server_storage'], username)
    if not os.path.exists(user_storage):
        os.mkdir(user_storage)
    files = os.listdir(user_storage)
    for n, file in enumerate(files):
        path = os.path.join(user_storage, file)
        if n < 4:
            file = file.replace(f'[{n + 1}]', f'[{n + 2}]')
            os.rename(path, os.path.join(user_storage, file))
        else:
            os.remove(path)
    with open(os.path.join(user_storage, create_filename()), 'wb') as zipf:
        zipf.write(gather_data(cl_connection))

    print('done')
    connection.send(b"done")


def server_downloading(cl_connection: socket.socket, files: list[str], username: str, n: int = 1) -> None:
    print("Sending data to the client...", end='')
    user_storage = os.path.join(settings['server_storage'], username)
    path = os.path.join(user_storage, files[n-1])
    cl_connection.send(os.path.getsize(path).to_bytes(16, 'big'))
    with open(path, "rb") as zipf:
        cl_connection.send(zipf.read())
    print(cl_connection.recv(4).decode())


sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_address = eval(settings['address'])
sock.bind(server_address)

print('Starting up on %s port %s' % server_address)

sock.listen()


def handle_client(conn, addr):
    print('Connected by', addr)
    while 1:
        try:
            conn.send(b'OK')
            username = conn.recv(16).decode()
            user_storage = os.path.join(settings['server_storage'], username)
            query = conn.recv(8).decode()  # upload, download, rollback or exit

            if query == 'upload':
                server_uploading(conn, username)

            elif query == 'download':
                server_downloading(conn, os.listdir(str(user_storage)), username)

            elif query == 'rollback':
                files = os.listdir(str(user_storage))
                files_to_show = files.copy()
                for n, file in enumerate(files):
                    files_to_show[n] = file.replace('_', ' ')
                    files_to_show[n] = files_to_show[n].replace('+', ':')
                vers_list = ("Choose number of version, you want to download.\nList of available versions:\n" +
                             "\n".join(files_to_show))
                conn.send(vers_list.encode())
                conn.send(len(files_to_show).to_bytes(2, 'big'))
                answer = conn.recv(4).decode()
                if answer == 'exit':
                    raise ValueError
                server_downloading(conn, files, username, int(answer))

            elif query == 'exit':
                raise ValueError

            if query == '/exit' and username == 'Vayneel':
                conn.close()
                sock.close()
                break

        except ValueError or socket.error:
            conn.close()
            print(f"Client {addr} disconnected")
            break


while sock:
    try:
        connection, address = sock.accept()
        thread = threading.Thread(target=handle_client, args=(connection, address))
        thread.start()
    except socket.error:
        break
