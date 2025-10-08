import wx
import socket
import threading
import select
import time
import random
import wx.richtext as rt
from typing import Optional, Dict, List

# Network configuration constants
SERVER_HOST = "localhost"
SERVER_PORT = 12345
CONNECTION_TIMEOUT = 5
RECONNECT_BASE_DELAY = 1
RECONNECT_MAX_DELAY = 16
RECEIVE_BUFFER_SIZE = 1024
NETWORK_POLL_INTERVAL = 0.05

# UI configuration constants
WINDOW_WIDTH = 500
WINDOW_HEIGHT = 420
SLEEP_INTERVAL = 0.05

# Message protocol constants
MSG_PREFIX = "MSG:"
NAME_PREFIX = "NAME:"
FROM_PREFIX = "FROM:"
SYS_PREFIX = "SYS:"


class ChatClient(wx.Frame):
    """
    Main chat client application window.
    
    This class handles the GUI interface and manages the network connection
    to the chat server. It provides a real-time chat experience with
    automatic reconnection and message formatting.
    """
    def __init__(self, parent, title: str):
        super(ChatClient, self).__init__(parent, title=title, size=(WINDOW_WIDTH, WINDOW_HEIGHT))
        
        # Initialize GUI components
        self._setup_gui()
        
        # Initialize networking state
        self._initialize_networking()
        
        # Initialize user interface state
        self._initialize_ui_state()
        
        # Start background networking thread
        self._start_networking_thread()

    def _setup_gui(self) -> None:
        self.panel = wx.Panel(self)
        
        # Create main chat display area
        self.chat_view = rt.RichTextCtrl(
            self.panel, 
            style=wx.TE_READONLY | wx.VSCROLL | wx.HSCROLL
        )
        
        # Create message input field
        self.input_text = wx.TextCtrl(
            self.panel, 
            style=wx.TE_PROCESS_ENTER
        )
        
        # Create send button
        self.send_button = wx.Button(self.panel, label="Send")

        # Bind event handlers
        self.send_button.Bind(wx.EVT_BUTTON, self.send_message)
        self.input_text.Bind(wx.EVT_TEXT_ENTER, self.send_message)
        self.Bind(wx.EVT_CLOSE, self.on_close)

        # Layout components using sizer
        self._layout_components()

    def _layout_components(self) -> None:
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Add chat view (takes most of the space)
        self.sizer.Add(
            self.chat_view, 
            proportion=1, 
            flag=wx.EXPAND | wx.ALL, 
            border=5
        )
        
        # Add input field
        self.sizer.Add(
            self.input_text, 
            flag=wx.EXPAND | wx.ALL, 
            border=5
        )
        
        # Add send button
        self.sizer.Add(
            self.send_button, 
            flag=wx.EXPAND | wx.ALL, 
            border=5
        )

        self.panel.SetSizer(self.sizer)

    def _initialize_networking(self) -> None:
        """Initialize networking-related instance variables."""
        self.client_socket: Optional[socket.socket] = None
        self.inputs: List[socket.socket] = []
        self.outputs: List[socket.socket] = []
        self.stop_event = threading.Event()

    def _initialize_ui_state(self) -> None:
        """Initialize UI-related state variables."""
        self.username = self._prompt_for_username()
        self.name_colors: Dict[str, wx.Colour] = {}
        self.pastel_palette = self._create_pastel_color_palette()

    def _create_pastel_color_palette(self) -> List[wx.Colour]:
        """Create a palette of pastel colors for user message bubbles."""
        return [
            wx.Colour(245, 245, 245),  # light gray fallback
            wx.Colour(255, 235, 238),  # light red
            wx.Colour(232, 245, 233),  # light green
            wx.Colour(232, 234, 246),  # light indigo
            wx.Colour(227, 242, 253),  # light blue
            wx.Colour(252, 228, 236),  # light pink
            wx.Colour(255, 249, 196),  # light yellow
            wx.Colour(240, 244, 195),  # light lime
            wx.Colour(248, 187, 208),  # pinkish
            wx.Colour(200, 230, 201),  # mint
        ]

    def _start_networking_thread(self) -> None:
        """Start the background networking thread."""
        self.net_thread = threading.Thread(
            target=self._network_loop, 
            daemon=True
        )
        self.net_thread.start()

    def send_message(self, event) -> None:
        message_text = self.input_text.GetValue().strip()
        
        # Don't send empty messages
        if not message_text:
            return
            
        # Clear the input field immediately for better UX
        self.input_text.Clear()
        
        try:
            if self.client_socket:
                # Format message according to protocol
                formatted_message = f"{MSG_PREFIX}{message_text}"
                message_bytes = formatted_message.encode("utf-8")
                
                # Send message to server
                self.client_socket.send(message_bytes)
            else:
                # Show error if not connected
                wx.CallAfter(self._append_system_message, "Not connected to server")
                
        except Exception as e:
            # Show error message if send fails
            wx.CallAfter(self._append_system_message, f"Failed to send message: {e}")

    def _network_loop(self) -> None:
        """
        Main networking loop that handles connection and message receiving.
        
        This method runs in a separate thread and continuously:
        1. Attempts to connect to the server if not connected
        2. Receives messages from the server
        3. Handles disconnections and reconnections
        """
        reconnect_delay = RECONNECT_BASE_DELAY
        
        while not self.stop_event.is_set():
            try:
                if not self.client_socket:
                    reconnect_delay = self._attempt_connection(reconnect_delay)
                    continue
                
                # Try to receive messages
                self._receive_messages()
                
                # Small pause to avoid busy loop
                self._sleep_interruptible(NETWORK_POLL_INTERVAL)
                
            except Exception as e:
                # Log unexpected errors and continue
                print(f"Network loop error: {e}")
                self._sleep_interruptible(0.5)

    def _attempt_connection(self, current_delay: int) -> int:
        """
        Attempt to connect to the chat server.
        
        Args:
            current_delay: Current reconnection delay in seconds
            
        Returns:
            Updated delay for next reconnection attempt
        """
        try:
            # Create new socket
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(CONNECTION_TIMEOUT)
            
            # Attempt connection
            self.client_socket.connect((SERVER_HOST, SERVER_PORT))
            self.client_socket.setblocking(False)
            
            # Set up select lists
            self.inputs = [self.client_socket]
            self.outputs = []
            
            # Send username to server
            self._send_username_handshake()
            
            # Connection successful
            wx.CallAfter(self._append_system_message, "Connected to chat server")
            return RECONNECT_BASE_DELAY  # Reset delay
            
        except Exception as e:
            # Connection failed
            wx.CallAfter(
                self._append_system_message, 
                f"Connection failed, retrying in {current_delay}s"
            )
            
            # Clean up failed connection
            self._cleanup_connection()
            
            # Wait before retry
            self._sleep_interruptible(current_delay)
            
            # Increase delay for next attempt (exponential backoff)
            return min(RECONNECT_MAX_DELAY, current_delay * 2)

    def _send_username_handshake(self) -> None:
        """Send username to server as part of connection handshake."""
        try:
            username_message = f"{NAME_PREFIX}{self.username}"
            self.client_socket.send(username_message.encode("utf-8"))
        except Exception as e:
            # Username send failed, but connection is still valid
            print(f"Failed to send username: {e}")

    def _cleanup_connection(self) -> None:
        """Clean up a failed or closed connection."""
        try:
            if self.client_socket:
                self.client_socket.close()
        except Exception:
            pass  # Ignore cleanup errors
        finally:
            self.client_socket = None

    def _receive_messages(self) -> None:
        """Receive and process messages from the server."""
        try:
            # Check for readable sockets
            readable_sockets, _, _ = select.select(
                self.inputs, [], self.inputs, 1
            )
        except Exception:
            readable_sockets = []
        
        for socket_fd in readable_sockets:
            try:
                # Receive data from socket
                received_data = socket_fd.recv(RECEIVE_BUFFER_SIZE)
            except Exception:
                received_data = b""
            
            if received_data:
                # Process received message
                message_text = received_data.decode("utf-8", errors="ignore")
                self._handle_incoming_message(message_text)
            else:
                # Socket closed by server
                self._handle_disconnection()

    def _handle_disconnection(self) -> None:
        """Handle disconnection from the server."""
        self._cleanup_connection()
        wx.CallAfter(self._append_system_message, "Disconnected from server; reconnecting...")

    def _prompt_for_username(self) -> str:
        """
        Prompt the user to enter their username.
        
        Returns:
            The username entered by the user, or a default name if cancelled
        """
        dialog = wx.TextEntryDialog(
            self, 
            "Enter your username:", 
            "Username", 
            value=""
        )
        
        try:
            if dialog.ShowModal() == wx.ID_OK:
                username = dialog.GetValue().strip()
                if username:
                    return username
        finally:
            dialog.Destroy()
        
        # Return default username if user cancelled or entered empty name
        timestamp = int(time.time()) % 100000
        return f"User-{timestamp}"

    def _handle_incoming_message(self, message_text: str) -> None:
        """
        Handle incoming messages from the server.
        
        Args:
            message_text: Raw message text received from server
        """
        message_text = message_text.strip()
        
        # Handle system messages
        if message_text.startswith(SYS_PREFIX):
            system_message = message_text[len(SYS_PREFIX):].strip()
            wx.CallAfter(self._append_system_message, system_message)
            return
        
        # Handle messages from other users
        if message_text.startswith(FROM_PREFIX):
            try:
                # Parse message format: FROM:username:message
                _, rest = message_text.split(FROM_PREFIX, 1)
                sender_name, message_content = rest.split(":", 1)
                sender_name = sender_name.strip()
                message_content = message_content.strip()
                
                # Display message based on sender
                if sender_name == self.username:
                    wx.CallAfter(self._append_own_message, message_content)
                else:
                    wx.CallAfter(self._append_other_message, sender_name, message_content)
                    
            except ValueError:
                # Malformed message, display as system message
                wx.CallAfter(self._append_system_message, message_text)
            return
        
        # Handle unknown message format
        wx.CallAfter(self._append_system_message, message_text)

    def _get_color_for_sender(self, sender_name: str) -> wx.Colour:
        """
        Get a unique color for a sender's messages.
        
        Args:
            sender_name: Name of the message sender
            
        Returns:
            wx.Colour object representing the sender's color
        """
        if sender_name not in self.name_colors:
            # Try to assign a color that's not heavily used
            color = random.choice(self.pastel_palette)
            
            # Check if this color is already used by other senders
            used_colors = set(
                (c.Red(), c.Green(), c.Blue()) 
                for c in self.name_colors.values()
            )
            
            # Try to find a less used color
            attempts = 0
            color_key = (color.Red(), color.Green(), color.Blue())
            
            while color_key in used_colors and attempts < 5:
                color = random.choice(self.pastel_palette)
                color_key = (color.Red(), color.Green(), color.Blue())
                attempts += 1
            
            self.name_colors[sender_name] = color
            
        return self.name_colors[sender_name]

    def _append_other_message(self, sender_name: str, message_content: str) -> None:
        """
        Append a message from another user to the chat display.
        
        Args:
            sender_name: Name of the message sender
            message_content: The message content
        """
        self.chat_view.Freeze()
        try:
            # Left-align messages from others
            self.chat_view.BeginAlignment(wx.TEXT_ALIGNMENT_LEFT)
            
            # Apply sender-specific background color
            background_color = self._get_color_for_sender(sender_name)
            text_attr = rt.RichTextAttr()
            text_attr.SetBackgroundColour(background_color)
            
            self.chat_view.BeginStyle(text_attr)
            self.chat_view.BeginTextColour(wx.Colour(20, 20, 20))  # Dark text
            self.chat_view.WriteText(f"{sender_name}: {message_content}")
            self.chat_view.EndTextColour()
            self.chat_view.EndStyle()
            self.chat_view.Newline()
            self.chat_view.EndAlignment()
            
        finally:
            self.chat_view.Thaw()

    def _append_own_message(self, message_content: str) -> None:
        """
        Append the user's own message to the chat display.
        
        Args:
            message_content: The message content
        """
        self.chat_view.Freeze()
        try:
            # Right-align own messages
            self.chat_view.BeginAlignment(wx.TEXT_ALIGNMENT_RIGHT)
            
            # Apply blue background for own messages
            text_attr = rt.RichTextAttr()
            text_attr.SetBackgroundColour(wx.Colour(225, 245, 254))  # Light blue
            
            self.chat_view.BeginStyle(text_attr)
            self.chat_view.BeginTextColour(wx.Colour(0, 51, 102))  # Dark blue text
            self.chat_view.WriteText(message_content)
            self.chat_view.EndTextColour()
            self.chat_view.EndStyle()
            self.chat_view.Newline()
            self.chat_view.EndAlignment()
            
        finally:
            self.chat_view.Thaw()

    def _append_system_message(self, message_content: str) -> None:
        """
        Append a system message to the chat display.
        
        Args:
            message_content: The system message content
        """
        self.chat_view.Freeze()
        try:
            # Center-align system messages
            try:
                center_alignment = wx.TEXT_ALIGNMENT_CENTRE
            except AttributeError:
                center_alignment = wx.TEXT_ALIGNMENT_CENTER
                
            self.chat_view.BeginAlignment(center_alignment)
            self.chat_view.BeginTextColour(wx.Colour(120, 120, 120))  # Gray text
            self.chat_view.BeginItalic()
            self.chat_view.WriteText(f"[SYSTEM] {message_content}")
            self.chat_view.EndItalic()
            self.chat_view.EndTextColour()
            self.chat_view.Newline()
            self.chat_view.EndAlignment()
            
        finally:
            self.chat_view.Thaw()

    def _sleep_interruptible(self, seconds: float) -> None:
        """
        Sleep for the specified duration, but can be interrupted by stop_event.
        
        Args:
            seconds: Number of seconds to sleep
        """
        end_time = time.time() + seconds
        while time.time() < end_time and not self.stop_event.is_set():
            time.sleep(SLEEP_INTERVAL)
    
    def on_close(self, event) -> None:
        """
        Handle application close event.
        
        Args:
            event: wxPython close event
        """
        # Signal networking thread to stop
        self.stop_event.set()
        
        # Close network connection
        try:
            if self.client_socket:
                self.client_socket.close()
        except Exception:
            pass  # Ignore cleanup errors
        
        # Destroy the window
        self.Destroy()

def main() -> None:
    """
    Main entry point for the chat client application.
    
    Creates and runs the wxPython application with the chat client window.
    """
    app = wx.App()
    chat_client = ChatClient(None, "Chat Client")
    chat_client.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()