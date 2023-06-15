"""
Модуль, содержащий модели SQLModel для приложения
"""
import json

from sqlmodel import SQLModel, Field
from typing import Optional
import re
from datetime import datetime


# region SQLModel модели

class User(SQLModel, table=True):
    """
    Модель для пользователя
    Поля:
    id: int - айди в базе,
    chat: str - строка с идентификатором диалога бота с пользователем,
    active: bool - посылать ли пользователю сообщения
    """

    __tablename__: str = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    chat: str
    active: bool


class Resource(SQLModel, table=True):
    """
    Модель для ресурса, который нужно пинговать
    Поля:
    id: int - айди в базе,
    address: str - адрес. Может быть представлен как в формате ip,
    так и в формате http(s):// адреса.
    Методы:
    validate(self) - Производит проверку адреса на корректность

    """
    __tablename__: str = "resources"

    id: Optional[int] = Field(default=None, primary_key=True)
    address: str
    name: str

    def from_dict(self, input_dict: dict):
        self.address = input_dict["address"]
        self.name = input_dict["name"]
        self.validate()
        return

    def validate(self):
        if not re.match(r"^(\d{1,3}\.){3}\d{1,3}$|^https?://.*$", self.address):
            raise ValueError("Неверный формат ввода")

    def serialize(self):
        return json.dumps({"id": self.id, "address": self.address, "name": self.name})


class JournalRow(SQLModel, table=True):
    """
    Модель для записи журнала недоступности
    Поля:
    id: int - идентификатор в базе
    resource: int - идентификатор ресурса
    created_at: datetime - дата недоступности ресурса
    """
    __tablename__: str = "journal"

    id: Optional[int] = Field(default=None, primary_key=True)
    resource: Optional[int] = Field(default=None, foreign_key="resources.id")
    created_at: datetime = Field(default_factory=datetime.now(), nullable=False)


# endregion
