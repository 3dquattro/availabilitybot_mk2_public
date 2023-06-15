"""
Основной модуль приложения
Содержит в себе описание команд aigram, часть методов взаимодействия с БД
"""

import datetime
import json
import redis
from celery import Celery, group
import celery.exceptions
from sqlmodel import create_engine, Session, select
from ping3 import ping
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import config.conf as config
from models import User, Resource, JournalRow


# region Объявление бота и подключение к БД
bot = Bot(config.token)
dp = Dispatcher(bot, storage=MemoryStorage())
redis_queue = redis.StrictRedis(host='localhost', port=6379, db=2)
params: dict = config.db_params
db_url: str = (
        ""
        + params["engine"]
        + "://"
        + params["user"]
        + ":"
        + params["password"]
        + "@"
        + params["host"]
        + ":"
        + params["port"]
        + "/"
        + params["db_name"]
)
engine = create_engine(db_url)

# endregion


# region Задачи Celery
app = Celery("main", backend='redis://localhost:6379', broker='redis://127.0.0.1:6379')
app.autodiscover_tasks()


@app.task
def ping_resource(resource: str):
    """
    Метод-задача пинга ресурса. Возвращает ответ/ ответ после n-количества попыток.
    :param resource: Ресурс, который нужно пинговать
    """
    dict_resource = json.loads(json.loads(resource))
    response = [ping(dict_resource['address'])]

    if response[0] not in [None, False]:
        return response[0]
    try:
        raise ping_resource.retry(max_retries=config.max_tries, countdown=8)
    except celery.exceptions.MaxRetriesExceededError:
        # Отправка сообщения в телеграм
        message = f"Ресурс {dict_resource['name']} недоступен после " \
                  f"{config.max_tries} попыток. Время: {datetime.datetime.now()}."
        for dialogue_id in addresates:
            # Добавляем в очередь сообщений
            redis_queue.rpush('messages', json.dumps({"dialogue": dialogue_id, "message": message}))
            add_journal_entry(dict_resource['id'])


@app.task
def check_resources(resources: list):
    """
    Метод для создания группы задач пинга в Celery.
    :return:
    """

    # Создаем группу задач Celery
    tasks = [ping_resource.si(json.dumps(resource)) for resource in resources]
    group(*tasks).apply_async()


def add_user(chat: str):
    """
    Метод-задача, служит для добавления пользователя (запись в бд).
    :param chat: str - Идентификатор чата с пользователем
    """
    with Session(engine) as session:
        query = select(User).where(User.chat == chat)
        result = session.exec(query)
        result = result.all()
        if not result:
            user = User(chat=chat, active=True)
        else:
            user = result[0]
            user.active = True
        session.add(user)
        session.commit()


def stop_sending_to_user(chat: str):
    """
    Метод, служащий для остановки рассылки для пользователя
    :param chat: str - Идентификатор чата с пользователем
    :return:
    """
    with Session(engine) as session:
        query = select(User).where(User.chat == chat)
        result = session.exec(query)
        if result is None:
            return
        user = result.one()
        user.active = False
        session.add(user)
        session.commit()
        return


async def add_journal_entry(resource_id: int):
    """
    Метод, добавляющий запись в журнал недоступности в базе
    :param resource_id: Недоступный ресурс
    """
    entry = JournalRow()
    entry.resource = resource_id
    with Session(engine) as session:
        session.add(entry)
        session.commit()
# endregion


# region Получение/обновление данных для работы бота
def get_dialogues() -> list:
    """
    Метод, возвращающий списка активных рассылок
    :return: result: list - Список активных рассылок
    """
    with Session(engine) as session:
        query = select(User.chat).where(User.active)
        result = session.exec(query)
        return list(result)


def get_resources() -> list:
    """
    Метод, возвращающий список ресурсов, которые нужно пинговать
    :return: result: list - Список ресурсов
    """
    with Session(engine) as session:
        query = select(Resource)
        result = session.exec(query)
        return result.all()


# Инициализация основных массивов
resources = get_resources()
addresates = get_dialogues()


# endregion


# region Обработчики команд и состояния
def add_resource(resource_dictionary: dict):
    """
    Метод добавляет из словаря, полученного от пользователя
    в базу данных ресурс для пингования
    :param resource_dictionary:
    """
    resource = Resource()
    try:
        resource.from_dict(resource_dictionary)
    except ValueError as exception:
        print(exception)
        return False
    with Session(engine) as session:
        session.add(resource)
        session.commit()
    return True


def remove_resource(id_to_remove: str) -> bool:
    """
    Метод, проверяющий возможность удаления и удаляющий ресурс
    :param id_to_remove: идентификатор удаляемого ресурса
    :return: True если удаление прошло успешно, false - в обратном случае
    """
    # Для начала, проверим ввод на целочисленность
    try:
        id = int(id_to_remove)
    except ValueError:
        return False
    with Session(engine) as session:
        query = select(Resource).where(id=id)
        results = session.exec(query)
        all_results = results.all()
        if len(all_results) == 0:
            return False
        session.delete(all_results[0])
        session.commit()
        return True


class AddResource(StatesGroup):
    """
    Класс, описывающий группу состояний для реализации
    команды /add_resource
    """
    waiting_for_address = State()
    waiting_for_name = State()


remove_state1 = State()


@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    """
    Обработчик команды /start
    Служит:
    1. Для записи id чата, в случае если пользователь еще не добавлялся
    2. Для активизации рассылки пользователю
    :param message: Сообщение aiogram
    """
    global addresates
    add_user(str(message.from_user.id))
    addresates = get_dialogues()
    await bot.send_message(message.from_user.id, "Рассылка сообщений активирована")


# Команда /stop останавливает рассылку сообщений
@dp.message_handler(commands=["stop"])
async def stop_handler(message: types.Message):
    """
    Обработчик команды /stop
    Ставит active = False для пользователя в базе
    :param message:
    """
    global addresates
    stop_sending_to_user(str(message.from_user.id))
    addresates = get_dialogues()
    await bot.send_message(message.from_user.id, "Рассылка сообщений остановлена")
    return


@dp.message_handler(commands='resource_list')
async def get_resources_command(message: types.Message):
    """
    Процедура-обработчик команды /resource_list
    Посылает в ответ сообщение со списком ресурсов
    :param message: Сообщение aiogram
    """

    text = 'Список ресурсов:\n'
    for resource in resources:
        text += f"{resource.id}.{resource.name} - {resource.address}.\n"
    await message.answer(text)


@dp.message_handler(commands="add_resource")
async def add_resource_step1(message: types.Message):
    """
    Процедура-обработчик первой стадии команды /add_resource
    Первый этап - запрос ввода адреса ресурса,
    переводит конечный автомат в промежуточное состояние
    :param message: Сообщение aiogram
    """
    await message.answer("Введите адрес ресурса:")
    await AddResource.waiting_for_address.set()


@dp.message_handler(state=AddResource.waiting_for_address)
async def add_resource_step2(message: types.Message, state: FSMContext):
    """
    Процедура-обработчик второй стадии команды /add_resource
    Сохраняет ввод адреса и запрашивает имя, переводя в финальный статус
    :param message: Сообщение aiogram
    :param state: Хранилище FSM
    """
    async with state.proxy() as data:
        data["address"] = message.text
    await message.answer("Введите имя ресурса:")
    await AddResource.waiting_for_name.set()


@dp.message_handler(state=AddResource.waiting_for_name)
async def add_resource_step3(message: types.Message, state: FSMContext):
    """
    Финальная стадия добавления ресурса, здесь завершение работы со статусами
    и отправка готового словаря характеристик в метод add_resource
    :param message: Сообщение aiogram
    :param state: Хранилище FSM
    """
    global resources
    async with state.proxy() as data:
        data["name"] = message.text
        address = data["address"]
        name = data["name"]
        result = add_resource({"address": address, "name": name})
    if result is True:
        await message.answer(f"Ресурс '{name}' по адресу '{address}' добавлен.")
        resources = get_resources()
    else:
        await message.answer("Ошибка, проверьте ввод!")
    await state.finish()


@dp.message_handler(commands='remove_resource')
async def remove_resource_step1(message: types.Message):
    """
    Обработчик команды remove_resource. Первый этап - смена состояния и запрос ввода
    :param message: Сообщение с командой
    :return:
    """
    await remove_state1.set()
    await message.answer("Введите идентификатор удаляемого ресурса:")


@dp.message_handler(state=remove_state1)
async def remove_resource_step2(message: types.Message, state: FSMContext):
    """
    Обработчик проверки ввода удаляемого ресурса и самого удаления.
    :param message: Сообщение с id
    :param state: Хранилище FSM
    :return:
    """
    global resources
    id_to_remove = message.text
    result = remove_resource(id_to_remove)
    if not result:
        await message.answer("Ошибка, проверьте ввод!")
    else:
        await message.answer(f"Ресурс {id_to_remove} успешно удалён!")
        resources = get_resources()
    await state.finish()
# endregion


# region async-процедуры для event-loop'а
async def mailing():
    """
    Процедура, производящая рассылку накопившихся сообщений
    :return:
    """
    # Пока очередь не опустела, шлём сообщения
    while redis_queue.llen('messages') > 0:
        message: dict = json.loads(redis_queue.lpop('messages'))
        if message:
            await bot.send_message(message['dialogue'], message['message'])


@app.on_after_finalize.connect
def setup_periodic_tasks(sender):
    """
    Запуск периодических задач
    :param sender: По логике, sender - экземпляр Celery
    :return:
    """

    resources_for_task = [resource.serialize() for resource in resources]
    sender.add_periodic_task(config.period,
                             check_resources.s(resources_for_task),
                             name='resources_check')


async def shutdown(dispatcher: Dispatcher):
    """
    Процедура, закрывающая соединение с telegram и чистящая хранилище.
    :param dispatcher: Aiogram диспетчер
    :return:
    """
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()


# endregion


scheduler = AsyncIOScheduler()
scheduler.add_job(mailing, 'interval', seconds=30)


if __name__ == "__main__":
    scheduler.start()
    executor.start_polling(dp, on_shutdown=shutdown, skip_updates=True)
