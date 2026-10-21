import unittest
import json
import time
import threading
import asyncio
from unittest.mock import MagicMock, AsyncMock
from host_agent.host_service import HostService
from host_agent.chat_window import HostChatWindow

class TestHostChat(unittest.TestCase):
    def test_send_chat_message(self):
        service = HostService(
            relay_url="ws://127.0.0.1:8080/ws",
            room_id="RD-TEST",
            pin="123456",
            device_name="TestHost"
        )
        loop = asyncio.new_event_loop()
        t = threading.Thread(target=loop.run_forever, daemon=True)
        t.start()
        try:
            service.ws = MagicMock()
            service.ws.send = AsyncMock()
            service.loop = loop

            service.send_chat_message("Xin chào client")
            time.sleep(0.05)
            self.assertTrue(service.ws.send.called)
            # Verify payload
            call_arg = json.loads(service.ws.send.call_args[0][0])
            self.assertEqual(call_arg["type"], "chat_message")
            self.assertEqual(call_arg["message"], "Xin chào client")
            self.assertEqual(call_arg["sender"], "TestHost")
        finally:
            loop.call_soon_threadsafe(loop.stop)

    def test_incoming_chat_message_dispatch(self):
        service = HostService(
            relay_url="ws://127.0.0.1:8080/ws",
            room_id="RD-TEST",
            pin="123456",
            device_name="TestHost"
        )
        received_messages = []
        service.on_chat_message = lambda sender, text: received_messages.append((sender, text))

        event = {
            "type": "chat_message",
            "sender": "Kỹ thuật viên",
            "message": "Tôi đang kiểm tra máy bạn nhé"
        }
        
        service.on_chat_message(event["sender"], event["message"])
        self.assertEqual(len(received_messages), 1)
        self.assertEqual(received_messages[0], ("Kỹ thuật viên", "Tôi đang kiểm tra máy bạn nhé"))

    def test_chat_window_headless(self):
        import sys
        import tkinter as tk
        replies = []

        if sys.platform == "darwin":
            try:
                root = tk.Tk()
                root.withdraw()
                chat = HostChatWindow(on_send_reply=lambda t: replies.append(t), parent=root)
            except Exception:
                self.skipTest("Tkinter display unavailable in test environment on macOS")
                return
        else:
            chat = HostChatWindow(on_send_reply=lambda t: replies.append(t))

        try:
            chat.add_message("Client", "Hello host", is_local=False)
            chat.show()
            chat.hide()
            if chat.on_send_reply:
                chat.on_send_reply("Hello client")
            self.assertEqual(replies, ["Hello client"])
        finally:
            if chat.root:
                try:
                    chat.root.after(0, chat.root.destroy)
                except Exception:
                    pass

if __name__ == "__main__":
    unittest.main()
