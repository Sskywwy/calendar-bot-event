import telebot
from telebot import types
import os
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime

# Токен вашого бота
api_token = "BotAPI"
bot = telebot.TeleBot(api_token)

# Доступ до Google Calendar API
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Функція для підключення до Google Calendar для кожного користувача
def connect_to_google_calendar(user_id):
    creds = None
    token_file = f'tokens/{user_id}_token.pickle'  # Унікальний файл для кожного користувача

    # Якщо існує файл з токеном
    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)

    # Якщо токен недійсний або відсутній, проходимо авторизацію
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Зберігаємо токен в файл
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)

    service = build('calendar', 'v3', credentials=creds)
    return service

# Створення події в Google Calendar
def create_event(service, summary, start_time, end_time, description=None, location=None):
    event = {
        'summary': summary,
        'location': location,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': 'UTC',  # Задайте свій часовий пояс
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'UTC',
        },
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 24 * 60},
                {'method': 'popup', 'minutes': 10},
            ],
        },
    }
    event = service.events().insert(calendarId='primary', body=event).execute()
    print(f'Подію створено: {event.get("htmlLink")}')
    return event

# Видалення події в Google Calendar
def delete_event(service, event_id):
    service.events().delete(calendarId='primary', eventId=event_id).execute()

# Клавіатура для меню
def keyboard_menu():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_add_event = types.KeyboardButton("Додати подію")
    button_delete = types.KeyboardButton("Видалити подію")
    button_list = types.KeyboardButton("Дивитися події")
    keyboard.add(button_add_event, button_delete, button_list)
    return keyboard

# Обробка команди /start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    token_file = f'tokens/{user_id}_token.pickle'
    if not os.path.exists(token_file):
        bot.send_message(message.chat.id, "Вітаю! Будь ласка, авторизуйтесь через Google, щоб я міг працювати з вашим календарем.")
        service = connect_to_google_calendar(user_id)  # Підключаємося до Google Calendar користувача
    bot.send_message(message.chat.id, "Авторизація пройшла успішно! Ви можете починати створювати події.")
    keyboard = keyboard_menu()
    bot.send_message(message.chat.id, "Оберіть дію:", reply_markup=keyboard)

# Обробка натискання кнопки "Додати подію"
@bot.message_handler(func=lambda message: message.text == "Додати подію")
def button_add_event_handler(message):
    user_id = message.from_user.id
    service = connect_to_google_calendar(user_id)
    add_event(message, service)

# Обробка натискання кнопки "Видалити подію"
@bot.message_handler(func=lambda message: message.text == "Видалити подію")
def button_delete_event_handler(message):
    user_id = message.from_user.id
    service = connect_to_google_calendar(user_id)
    delete_event_handler(message, service)

# Обробка натискання кнопки "Дивитися події"
@bot.message_handler(func=lambda message: message.text == "Дивитися події")
def button_list_event_handler(message):
    user_id = message.from_user.id
    service = connect_to_google_calendar(user_id)
    bot.send_message(message.chat.id, list_events(service))

# Функція для видалення події
def delete_event_handler(message, service):
    events_list = list_events(service)  # Отримуємо список подій
    if events_list:
        events_text = "\n".join(events_list)  # Перетворюємо список подій на текст
        bot.send_message(message.chat.id, f"Ось події у вашому календарі:\n{events_text}\nВведіть номер події для видалення:")
        bot.register_next_step_handler(message, process_event_deletion, service)
    else:
        bot.send_message(message.chat.id, "У вашому календарі немає подій для видалення.")

# Обробка видалення події за номером
def process_event_deletion(message, service):
    try:
        event_number = int(message.text)  # Отримуємо номер події, яку хоче видалити користувач
        events = service.events().list(calendarId='primary').execute()

        # Знаходимо відповідну подію за номером
        event = events['items'][event_number - 1]
        event_id = event['id']  # Отримуємо eventId події

        # Видаляємо подію
        delete_event(service, event_id)
        bot.send_message(message.chat.id, f"Подія '{event['summary']}' видалена успішно!")
    
    except (IndexError, ValueError):
        bot.send_message(message.chat.id, "Невірний номер події. Спробуйте ще раз.")
        bot.register_next_step_handler(message, process_event_deletion, service)
    except Exception as e:
        bot.send_message(message.chat.id, f"Сталася помилка: {str(e)}")

# Отримання списку подій
def list_events(service):
    events = service.events().list(calendarId='primary').execute()
    event_list = []
    for i, event in enumerate(events['items']):
        event_summary = event.get("summary", "Без назви")
        event_description = event.get("description", "Без опису")
        event_list.append(f"{i + 1}. {event_summary} - {event_description}")
    if len(event_list) ==  0:
        text = "Немає подій"
        return text
    else:
        return event_list

# Функція для додавання події
event_data = {}

def add_event(message, service):
    bot.send_message(message.chat.id, "Введіть назву події:")
    bot.register_next_step_handler(message, get_event_name, service)

def get_event_name(message, service):
    event_data['summary'] = message.text
    bot.send_message(message.chat.id, "Введіть дату початку події у форматі РРРР-ММ-ДД (наприклад, 2024-10-15):")
    bot.register_next_step_handler(message, get_event_date_start, service)

def get_event_date_start(message, service):
    try:
        event_data['start_date'] = datetime.strptime(message.text, '%Y-%m-%d').date()
        bot.send_message(message.chat.id, "Введіть дату кінця події у форматі РРРР-ММ-ДД (наприклад, 2024-10-15):")
        bot.register_next_step_handler(message, get_event_date_end, service)
    except ValueError:
        bot.send_message(message.chat.id, "Невірний формат дати. Спробуйте ще раз.")
        bot.register_next_step_handler(message, get_event_date_start, service)

def get_event_date_end(message, service):
    try:
        event_data['end_date'] = datetime.strptime(message.text, '%Y-%m-%d').date()
        bot.send_message(message.chat.id, "Введіть час початку події у форматі ГГ:ХХ (наприклад, 14:30):")
        bot.register_next_step_handler(message, get_event_time_start, service)
    except ValueError:
        bot.send_message(message.chat.id, "Невірний формат дати. Спробуйте ще раз.")
        bot.register_next_step_handler(message, get_event_date_end, service)

def get_event_time_start(message, service):
    try:
        event_data['start_time'] = datetime.strptime(message.text, '%H:%M').time()
        bot.send_message(message.chat.id, "Введіть час кінця події у форматі ГГ:ХХ (наприклад, 14:30):")
        bot.register_next_step_handler(message, get_event_time_end, service)
    except ValueError:
        bot.send_message(message.chat.id, "Невірний формат часу. Спробуйте ще раз.")
        bot.register_next_step_handler(message, get_event_time_start, service)

def get_event_time_end(message, service):
    try:
        event_data['end_time'] = datetime.strptime(message.text, '%H:%M').time()
        bot.send_message(message.chat.id, "Введіть опис події (або пропустіть, надіславши 'пропустити'):")
        bot.register_next_step_handler(message, get_event_description, service)
    except ValueError:
        bot.send_message(message.chat.id, "Невірний формат часу. Спробуйте ще раз.")
        bot.register_next_step_handler(message, get_event_time_end, service)

def get_event_description(message, service):
    event_data['description'] = message.text if message.text.lower() != 'пропустити' else None
    start_time = datetime.combine(event_data['start_date'], event_data['start_time'])
    end_time = datetime.combine(event_data['end_date'], event_data['end_time'])
    create_event(service, event_data['summary'], start_time.isoformat(), end_time.isoformat(), event_data['description'])
    bot.send_message(message.chat.id, f"Подія '{event_data['summary']}' створена!")






bot.infinity_polling()
