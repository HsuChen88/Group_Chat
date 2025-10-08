"""
Chat Server Application

A GUI-based chat server that manages multiple client connections and
relays messages between clients. Features include:
- Multi-client support using select() for non-blocking I/O
- Real-time message broadcasting
- Client connection management
- Server status monitoring through GUI

Author: Chat Application Team
"""

import wx
import socket
import threading
import select
from typing import Dict, List, Optional, Tuple

# Server configuration constants
SERVER_HOST = "localhost"
SERVER_PORT = 12345
MAX_CONNECTIONS = 5
RECEIVE_BUFFER_SIZE = 1024

# Message protocol constants
MSG_PREFIX = "MSG:"
NAME_PREFIX = "NAME:"
FROM_PREFIX = "FROM:"
SYS_PREFIX = "SYS:"

# GUI configuration constants
WINDOW_WIDTH = 400
WINDOW_HEIGHT = 300


class ChatServerGUI(wx.Frame):
    """
    GUI interface for the chat server.
    
    This class provides a simple text display window that shows server
    status messages, client connections, and chat activity.
    """
    def __init__(self, parent, title: str):
        """
        Initialize the chat server GUI.
        
        Args:
            parent: Parent window (usually None for main window)
            title: Window title
        """
        super(ChatServerGUI, self).__init__(
            parent, 
            title=title, 
            size=(WINDOW_WIDTH, WINDOW_HEIGHT)
        )

        # Set up GUI components
        self._setup_gui()
        
        # Initialize and start the chat server
        self.server = ChatServer(self)

        # Bind close event
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def _setup_gui(self) -> None:
        """Set up the graphical user interface components."""
        self.panel = wx.Panel(self)
        
        # Create text display area for server logs
        self.text_ctrl = wx.TextCtrl(
            self.panel, 
            style=wx.TE_MULTILINE | wx.TE_READONLY
        )
        
        # Layout components
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(
            self.text_ctrl, 
            proportion=1, 
            flag=wx.EXPAND | wx.ALL, 
            border=5
        )
        self.panel.SetSizer(self.sizer)

    def log_message(self, message: str) -> None:
        """
        Log a message to the GUI display.
        
        This method is thread-safe and can be called from the server thread.
        
        Args:
            message: Message to display in the log
        """
        wx.CallAfter(self._update_text_display, message)

    def _update_text_display(self, message: str) -> None:
        """
        Update the text display with a new message.
        
        Args:
            message: Message to append to the display
        """
        self.text_ctrl.AppendText(message + "\n")

    def on_close(self, event) -> None:
        """
        Handle application close event.
        
        Args:
            event: wxPython close event
        """
        # Stop the server
        self.server.stop_server()
        
        # Exit the application
        wx.GetApp().ExitMainLoop()
        event.Skip()


class ChatServer:
    """
    Main chat server that handles client connections and message routing.
    
    This class manages multiple client connections using non-blocking I/O
    with select(), handles message protocol, and broadcasts messages
    between connected clients.
    """
    
    def __init__(self, gui: ChatServerGUI):
        """
        Initialize the chat server.
        
        Args:
            gui: Reference to the GUI for logging messages
        """
        self.gui = gui
        
        # Initialize server socket
        self._setup_server_socket()
        
        # Initialize connection management
        self._initialize_connection_management()
        
        # Start server thread
        self._start_server_thread()

    def _setup_server_socket(self) -> None:
        """Set up the server socket for accepting connections."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.setblocking(False)
        self.server_socket.bind((SERVER_HOST, SERVER_PORT))
        self.server_socket.listen(MAX_CONNECTIONS)

    def _initialize_connection_management(self) -> None:
        """Initialize data structures for managing client connections."""
        # Socket lists for select()
        self.input_sockets = [self.server_socket]
        self.output_sockets = []
        self.exceptional_sockets = []
        
        # Message queues for each client
        self.message_queues: Dict[socket.socket, List[bytes]] = {}
        
        # Client name mapping
        self.client_names: Dict[socket.socket, str] = {}
        
        # Server control
        self.stop_event = threading.Event()

    def _start_server_thread(self) -> None:
        """Start the server thread for handling connections."""
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.start()

    def _run_server(self) -> None:
        """
        Main server loop that handles client connections and messages.
        
        This method runs in a separate thread and continuously:
        1. Accepts new client connections
        2. Receives messages from clients
        3. Broadcasts messages to all connected clients
        4. Handles client disconnections
        """
        self.gui.log_message("Server started. Waiting for connections.")
        
        while not self.stop_event.is_set():
            try:
                # Wait for socket activity
                readable_sockets, writable_sockets, exceptional_sockets = select.select(
                    self.input_sockets, 
                    self.output_sockets, 
                    self.exceptional_sockets
                )
                
                # Handle readable sockets (new connections and incoming messages)
                self._handle_readable_sockets(readable_sockets)
                
                # Handle writable sockets (send queued messages)
                self._handle_writable_sockets(writable_sockets)
                
                # Handle exceptional sockets (connection errors)
                self._handle_exceptional_sockets(exceptional_sockets)
                
            except Exception as e:
                # Log unexpected errors and continue
                self.gui.log_message(f"Server error: {e}")

    def _handle_readable_sockets(self, readable_sockets: List[socket.socket]) -> None:
        """
        Handle sockets that have data ready to read.
        
        Args:
            readable_sockets: List of sockets ready for reading
        """
        for socket_fd in readable_sockets:
            if socket_fd is self.server_socket:
                # New client connection
                self._accept_new_client(socket_fd)
            else:
                # Existing client sending data
                self._handle_client_data(socket_fd)

    def _accept_new_client(self, server_socket: socket.socket) -> None:
        """
        Accept a new client connection.
        
        Args:
            server_socket: The server socket accepting connections
        """
        try:
            client_socket, client_address = server_socket.accept()
            client_socket.setblocking(False)
            
            # Add to socket lists
            self.input_sockets.append(client_socket)
            self.output_sockets.append(client_socket)
            
            # Initialize message queue
            self.message_queues[client_socket] = []
            
            self.gui.log_message(f"New connection from {client_address}")
            
        except Exception as e:
            self.gui.log_message(f"Failed to accept connection: {e}")

    def _handle_client_data(self, client_socket: socket.socket) -> None:
        """
        Handle data received from a client.
        
        Args:
            client_socket: The client socket that sent data
        """
        try:
            received_data = client_socket.recv(RECEIVE_BUFFER_SIZE)
            
            if received_data:
                # Process received message
                message_text = received_data.decode("utf-8", errors="ignore").strip()
                self._process_client_message(client_socket, message_text)
            else:
                # Client disconnected
                self._handle_client_disconnection(client_socket)
                
        except Exception as e:
            self.gui.log_message(f"Error handling client data: {e}")
            self._handle_client_disconnection(client_socket)

    def _process_client_message(self, client_socket: socket.socket, message_text: str) -> None:
        """
        Process a message received from a client.
        
        Args:
            client_socket: The client socket that sent the message
            message_text: The message text to process
        """
        # Check if client has registered a name
        if client_socket not in self.client_names:
            self._handle_name_registration(client_socket, message_text)
        else:
            self._handle_chat_message(client_socket, message_text)

    def _handle_name_registration(self, client_socket: socket.socket, message_text: str) -> None:
        """
        Handle client name registration.
        
        Args:
            client_socket: The client socket registering
            message_text: The name registration message
        """
        if message_text.startswith(NAME_PREFIX):
            username = message_text[len(NAME_PREFIX):].strip()
            
            if not username:
                username = str(client_socket.getpeername())
            
            self.client_names[client_socket] = username
            
            # Broadcast join message to all clients
            join_message = f"{SYS_PREFIX}{username} joined"
            self.gui.log_message(join_message)
            self._broadcast_message(join_message)
        else:
            # Ignore messages until name is registered
            pass

    def _handle_chat_message(self, client_socket: socket.socket, message_text: str) -> None:
        """
        Handle a chat message from a registered client.
        
        Args:
            client_socket: The client socket that sent the message
            message_text: The chat message
        """
        if message_text.startswith(MSG_PREFIX):
            message_content = message_text[len(MSG_PREFIX):].strip()
            username = self.client_names.get(client_socket, str(client_socket.getpeername()))
            
            # Create relay message
            relay_message = f"{FROM_PREFIX}{username}:{message_content}"
            
            # Log message
            self.gui.log_message(f"{username}: {message_content}")
            
            # Broadcast to all clients
            self._broadcast_message(relay_message)
        else:
            # Unknown message format, ignore
            pass

    def _broadcast_message(self, message: str) -> None:
        """
        Broadcast a message to all connected clients.
        
        Args:
            message: The message to broadcast
        """
        message_bytes = message.encode("utf-8")
        
        for client_socket in list(self.message_queues.keys()):
            try:
                self.message_queues[client_socket].append(message_bytes)
            except Exception:
                # Client may have disconnected, will be cleaned up later
                pass

    def _handle_client_disconnection(self, client_socket: socket.socket) -> None:
        """
        Handle a client disconnection.
        
        Args:
            client_socket: The client socket that disconnected
        """
        # Get client name before cleanup
        username = self.client_names.pop(client_socket, None)
        
        # Log disconnection
        self.gui.log_message(f"Client disconnected: {client_socket.getpeername()}")
        
        # Clean up socket
        self._cleanup_client_socket(client_socket)
        
        # Broadcast leave message if client was registered
        if username:
            leave_message = f"{SYS_PREFIX}{username} left"
            self.gui.log_message(leave_message)
            self._broadcast_message(leave_message)

    def _cleanup_client_socket(self, client_socket: socket.socket) -> None:
        """
        Clean up resources associated with a client socket.
        
        Args:
            client_socket: The client socket to clean up
        """
        try:
            # Remove from socket lists
            if client_socket in self.input_sockets:
                self.input_sockets.remove(client_socket)
            if client_socket in self.output_sockets:
                self.output_sockets.remove(client_socket)
            
            # Close socket
            client_socket.close()
            
            # Remove from data structures
            self.message_queues.pop(client_socket, None)
            self.client_names.pop(client_socket, None)
            
        except Exception as e:
            self.gui.log_message(f"Error cleaning up client socket: {e}")

    def _handle_writable_sockets(self, writable_sockets: List[socket.socket]) -> None:
        """
        Handle sockets that are ready for writing.
        
        Args:
            writable_sockets: List of sockets ready for writing
        """
        for client_socket in writable_sockets:
            try:
                if client_socket in self.message_queues and self.message_queues[client_socket]:
                    # Send next queued message
                    message_bytes = self.message_queues[client_socket].pop(0)
                    client_socket.send(message_bytes)
            except Exception:
                # Send failed, mark for cleanup
                self.exceptional_sockets.append(client_socket)

    def _handle_exceptional_sockets(self, exceptional_sockets: List[socket.socket]) -> None:
        """
        Handle sockets with exceptional conditions.
        
        Args:
            exceptional_sockets: List of sockets with exceptional conditions
        """
        for client_socket in exceptional_sockets:
            self._handle_client_disconnection(client_socket)
            if client_socket in self.exceptional_sockets:
                self.exceptional_sockets.remove(client_socket)

    def stop_server(self) -> None:
        """Stop the chat server and clean up resources."""
        self.stop_event.set()
        
        # Close server socket
        try:
            self.server_socket.close()
        except Exception:
            pass


def main() -> None:
    """
    Main entry point for the chat server application.
    
    Creates and runs the wxPython application with the chat server window.
    """
    app = wx.App(False)
    server_gui = ChatServerGUI(None, title="Chat Server")
    server_gui.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
