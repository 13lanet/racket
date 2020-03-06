import socket
import errno
from threading import Thread


class Client:
    """Client class that deals with all of the client operations."""

    def __init__(self, socket, address, parent):
        """Sets up client."""
        self.socket = socket
        self.address = address
        self.parent = parent

        self.chat = False  # if the client has gotten to the chat stage

    def send(self, msg):
        """Takes a utf-8 message and sends the raw bytes to the client."""
        # clears the current line and resets cursor
        clear = "\033[1K\r"
        if not self.chat:
            raw = bytes("{}{}".format(clear, msg), "utf-8")
        else:
            msg += "\n" if msg else ""
            raw = bytes("{}{}\033[33m>\033[0m ".format(clear, msg), "utf-8")
        self.socket.send(raw)

    def recv(self):
        """Receives a utf-8 string from the client."""
        raw = self.socket.recv(self.parent.buffer_length)
        if self.chat:  # reset cursor
            self.send("")
        return raw.decode("utf-8")

    def msg(self, msg):
        """Sends a chat message."""
        # clears all trailing whitespace
        msg = msg.strip()
        full_msg = "\033[36m{}\033[0m: {}".format(self.name, msg)
        self.parent.broadcast(full_msg, self)

    def join(self):
        """Deals with the client joining the chat."""
        self.send("Enter your name\n> ")
        self.name = self.recv().strip()

        welcome = "Hi {}! Type :quit to leave\n".format(self.name)
        self.send(welcome)

        msg = "\033[32m{} has joined\033[0m".format(self.name)
        self.parent.broadcast(msg)

        # add to client list
        self.parent.clients[self] = self.name

    def leave(self, delete=True, gone=False):
        """Disconnects the client."""
        self.chat = False  # the client can no longer chat
        if not gone:
            self.send("You will be disconnected. Bye!")
        self.kill(delete)
        if delete:
            message = "\033[32m{} has left the chat\033[0m".format(self.name)
            self.parent.broadcast(message)

    def kill(self, delete):
        """Kills the socket connection."""
        # close socket
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()
        except Exception as e:
            # 32 and 107 are errors to do with connection being broken
            if e.args[0] not in [32, 107]:
                raise
        print("{} has left".format(self.address))
        if delete:
            del self.parent.clients[self]

    def handler(self):
        """Main method to handle client stuff."""
        self.join()
        self.chat = True
        self.send("")

        while True:
            message = self.recv()
            if ":quit" in message:
                self.leave()
                break
            elif message in ["", "\n"]:
                continue
            else:
                self.msg(message)

    def handle(self):
        """Wrapper to contain errors from self.handler()."""
        try:
            self.handler()
        except socket.error as e:
            if isinstance(e.args, tuple):
                # user disconnects
                if e.args[0] == errno.EPIPE:  # user closes socket
                    self.leave(gone=True)
                    return
                elif e.args[0] == 9:  # socket has already closed
                    return
            raise


class Server:
    """Server class that handles the server jobs."""
    def __init__(self, host, port):
        self.clients = {}

        self.host = host
        self.port = port
        self.buffer_length = 1024
        self.address = (self.host, self.port)

        # set up socket server
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(self.address)
        self.server.settimeout(1)

        self.is_running = False

    def start(self, connections):
        """Starts listening."""
        self.server.listen(connections)
        print("{}:{} is now available...".format(self.host, self.port))
        self.is_running = True

        try:
            accept_thread = Thread(target=self.accept_connections)
            accept_thread.start()
            accept_thread.join()
        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            self.is_running = False
            self.close_connections()

    def accept_connections(self):
        """Waits for clients to join."""
        while self.is_running:
            # we wait 1 second for the user
            try:
                client_socket, client_address = self.server.accept()
            except socket.timeout:
                if not self.is_running:  # check the server hasn't stopped
                    break
                else:
                    continue  # attempt to get another connection

            if not self.is_running:
                # close the new connection
                client_socket.close()
                break

            print("{} has joined".format(client_address))

            client = Client(client_socket, client_address, self)
            Thread(target=client.handle).start()

        self.close()

    def broadcast(self, message, sender=None):
        """Broadcasts message to all clients."""
        for client in self.clients:
            if client == sender:
                continue
            client.send(message)

    def close_connections(self):
        """Disconnects all clients."""
        self.broadcast("Closing server...")
        for client in self.clients:
            client.leave(delete=False)

    def close(self):
        """Shuts the server."""
        self.server.close()
        print("Closed server")


def main():
    server = Server("localhost", 1337)
    server.start(5)


if __name__ == "__main__":
    main()
