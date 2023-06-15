"""
Модуль, содержащий тесты. Использует pytest+unittest.mock
"""
import pytest
import unittest
import aiogram_unittest
from unittest.mock import MagicMock, Mock, patch
from aiogram import types
from aiogram_unittest import Requester
from aiogram_unittest.types.dataset import MESSAGE
from aiogram_unittest.handler import MessageHandler
from main import add_user, get_dialogues, start_handler


class TestBot(unittest.IsolatedAsyncioTestCase):
    async def start_message_handler(self):
        engine_mock = Mock()
        with(patch("engine", engine_mock)):
            requester = Requester(request_handler=MessageHandler(start_handler))

            message = MESSAGE.as_object("/start")
            calls = await requester.query(message)

            answer_message = calls.send_message.fetchone().text
            self.assertEqual(answer_message, "Рассылка сообщений активирована")


