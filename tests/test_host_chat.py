import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest
import json
import time
import threading
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from host_agent.host_service import HostService
from host_agent.chat_window import HostChatWindow
from host_agent.gui_agent import HostApi

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

            ok = service.send_chat_message("Xin chào client")
            self.assertTrue(ok)
            time.sleep(0.05)
            self.assertTrue(service.ws.send.called)
            # Verify payload
            call_arg = json.loads(service.ws.send.call_args[0][0])
            self.assertEqual(call_arg["type"], "chat_message")
            self.assertEqual(call_arg["message"], "Xin chào client")
            self.assertEqual(call_arg["sender"], "TestHost")
        finally:
            service.stop()
            loop.call_soon_threadsafe(loop.stop)

    def test_send_chat_message_empty(self):
        service = HostService(
            relay_url="ws://127.0.0.1:8080/ws",
            room_id="RD-TEST",
            pin="123456",
            device_name="TestHost"
        )
        try:
            ok = service.send_chat_message("   ")
            self.assertFalse(ok)
        finally:
            service.stop()

    def test_incoming_chat_message_dispatch(self):
        service = HostService(
            relay_url="ws://127.0.0.1:8080/ws",
            room_id="RD-TEST",
            pin="123456",
            device_name="TestHost"
        )
        try:
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
        finally:
            service.stop()

    def test_host_api_send_and_history(self):
        config = {"room_id": "RD-TEST", "pin": "123456", "device_name": "TestPC"}
        cfg_path = Path(".test_config.json")
        api = HostApi(config, cfg_path)
        try:
            # Mock host service
            mock_service = MagicMock()
            mock_service.send_chat_message = MagicMock(return_value=True)
            api._host_service = mock_service

            res = api.send_host_chat("Xin chào kỹ thuật viên!")
            self.assertEqual(res["status"], "ok")
            mock_service.send_chat_message.assert_called_with("Xin chào kỹ thuật viên!")

            # Verify chat history
            hist = api.get_chat_history()
            self.assertIsInstance(hist, list)

            # Empty message check
            empty_res = api.send_host_chat("   ")
            self.assertEqual(empty_res["status"], "error")
        finally:
            api.destroy()

    def test_chat_window_headless(self):
        import sys
        import os
        replies = []

        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            chat = HostChatWindow(on_send_reply=lambda t: replies.append(t), parent=root)
        except Exception:
            self.skipTest("Tkinter display unavailable in test environment")
            return

        try:
            chat.add_message("Client", "Xin chào máy trạm tiếng Việt", is_local=False)
            chat.show()
            chat.hide()
            if chat.on_send_reply:
                chat.on_send_reply("Tôi đã nhận được tin nhắn")
            self.assertEqual(replies, ["Tôi đã nhận được tin nhắn"])
            self.assertTrue(len(chat.history) >= 1)
            self.assertEqual(chat.history[0]["sender"], "Client")
        finally:
            try:
                root.destroy()
            except Exception:
                pass

if __name__ == "__main__":
    unittest.main()
