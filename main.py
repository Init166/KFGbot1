import os
import logging
from datetime import datetime
import telebot
import attendance_db
from telebot import types
import elders
import priority_db
import grades_db
import students
from database import check_schedule_days
from config import TOKEN
from schedule_utils import get_week_type
import database
import time

# Настройка логирования
log_folder = "loggs"
if not os.path.exists(log_folder):
    os.makedirs(log_folder)

today_date = datetime.now().strftime("%Y-%m-%d")
log_file = os.path.join(log_folder, f"logs_{today_date}.txt")

logging.basicConfig(
    level=logging.INFO,
    format=u'%(filename)20s [LINE:%(lineno)-4s] %(levelname)-8s [%(asctime)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8', mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = telebot.TeleBot(TOKEN)

# Инициализация баз данных
attendance_db.init_attendance_db()
grades_db.init_grades_db()
priority_db.init_priority_db()
logger.info("Бот запущен и готов к работе.")

# Временные данные
temp_data = {}
auth_states = {}
temp_storage = {}

def send_main_menu(chat_id):
    """Отправка главного меню после успешной авторизации."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Большая кнопка сверху
    btn_schedule = types.InlineKeyboardButton(
        text="📅 Расписание на эту неделю", 
        callback_data="view_schedule"
    )
    # Кнопки снизу: Табель и Пропуски
    btn_grades = types.InlineKeyboardButton(
        text="📝 Табель", 
        callback_data="view_grades"
    )
    btn_attendance = types.InlineKeyboardButton(
        text="✅ Пропуски", 
        callback_data="view_attendance"
    )
    # Нижний ряд: одна большая кнопка
    btn_priority = types.InlineKeyboardButton(
        text="🔥 Приоритет",
        callback_data="view_priority"
    )

    # Добавляем кнопки в разметку
    markup.add(btn_schedule)          # первая строка - одна кнопка
    markup.add(btn_grades, btn_attendance)  # вторая строка - две кнопки
    markup.add(btn_priority)                # третья строка
    
    bot.send_message(chat_id, "Выберите нужный функционал:", reply_markup=markup)

def split_long_message(text, max_length=4000):
    """Разбивает длинный текст на части."""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break
        
        split_pos = text.rfind('\n', 0, max_length)
        if split_pos == -1:
            split_pos = text.rfind(' ', 0, max_length)
            if split_pos == -1:
                split_pos = max_length
        
        parts.append(text[:split_pos])
        text = text[split_pos:].lstrip()
    
    return parts

def is_elder(user_id):
    """Проверяет, является ли пользователь старостой."""
    return elders.get_elder_info(user_id) is not None

def send_main_menu_button(chat_id, text="Выберите действие:"):
    """Отправляет сообщение с кнопкой главного меню"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    bot.send_message(chat_id, text, reply_markup=markup)

# ==================== ВРЕМЕННОЕ ХРАНИЛИЩЕ (из старого кода) ====================

def store_temp_data(user_id, data_type, data, ttl=300):
    """Сохраняет временные данные с TTL (по умолчанию 5 минут)"""
    if user_id not in temp_storage:
        temp_storage[user_id] = {}
    
    temp_storage[user_id][data_type] = {
        'data': data,
        'timestamp': time.time(),
        'ttl': ttl
    }

def get_temp_data(user_id, data_type):
    """Получает временные данные, если они не устарели"""
    if user_id not in temp_storage:
        return None
    
    if data_type not in temp_storage[user_id]:
        return None
    
    item = temp_storage[user_id][data_type]
    if time.time() - item['timestamp'] > item['ttl']:
        del temp_storage[user_id][data_type]
        return None
    
    return item['data']

# ==================== СТАРТ И АВТОРИЗАЦИЯ ====================

@bot.message_handler(commands=['start'])
def start_message(message):
    logger.info(f"Пользователь {message.from_user.id} вызвал /start")
    
    text = (
        "👋 Привет!\n\n"
        "Бот был создан для мониторинга расписания, табеля успеваемости, "
        "пропусков, дат выходных и сессий.\n\n"
        "📚 Здесь вся самая актуальная информация.\n\n"
        "Выберите свою группу:"
    )

    markup = types.InlineKeyboardMarkup()
    btn_group = types.InlineKeyboardButton(text="СПД-103", callback_data="group_SPD103")
    markup.add(btn_group)
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "group_SPD103")
def handle_group_selection(call):
    logger.info(f"Пользователь {call.from_user.id} выбрал группу СПД-103")
    bot.answer_callback_query(call.id)

    text = "✅ Группа СПД-103 выбрана!\n\nДля доступа к функциям бота требуется авторизация старосты."
    
    markup = types.InlineKeyboardMarkup()
    btn_leader = types.InlineKeyboardButton(text="🧑‍🏫 Авторизация старосты", callback_data="role_leader")
    markup.add(btn_leader)

    bot.send_message(call.message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["role_leader", "role_student"])
def handle_role_selection(call):
    if call.data == "role_leader":
        logger.info(f"Пользователь {call.from_user.id} выбрал роль: Староста")
        auth_states[call.from_user.id] = {"step": "login", "login": None, "role": "elder"}
        bot.send_message(call.message.chat.id, "🧑‍🏫 Вы выбрали роль Староста.\nВведите ваш логин:")
    else:
        logger.info(f"Пользователь {call.from_user.id} выбрал роль: Абитуриент")
        auth_states[call.from_user.id] = {"step": "login", "login": None, "role": "student"}
        bot.send_message(call.message.chat.id, "🎓 Вы выбрали роль Абитуриент.\nВведите ваш логин:")
    
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: message.from_user.id in auth_states)
def handle_auth(message):
    user_id = message.from_user.id
    state = auth_states[user_id]

    try:
        if state["step"] == "login":
            state["login"] = message.text.strip()
            state["step"] = "password"
            bot.send_message(message.chat.id, "Введите пароль:")
            
        elif state["step"] == "password":
            login = state["login"]
            password = message.text.strip()

            if state["role"] == "elder":
                conn = database.create_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT password_hash FROM elders WHERE login = ?", (login,))
                row = cursor.fetchone()
                conn.close()

                if row and database.hash_password(password) == row[0]:
                    bot.send_message(message.chat.id, f"✅ Авторизация успешна! Добро пожаловать, {login}.")
                    logger.info(f"Пользователь {user_id} успешно авторизован как староста ({login})")
                    send_main_menu(message.chat.id)
                    
                    conn = database.create_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE elders SET telegram_id = ? WHERE login = ?", (user_id, login))
                    conn.commit()
                    conn.close()
                else:
                    bot.send_message(message.chat.id, "❌ Неверный логин или пароль.")
            else:
                conn = database.create_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT password_hash, group_name FROM students WHERE name = ?", (login,))
                row = cursor.fetchone()
                conn.close()

                if row and database.hash_password(password) == row[0]:
                    group_name = row[1]
                    bot.send_message(message.chat.id, f"✅ Авторизация успешна! Добро пожаловать, {login}.\nВаша группа: {group_name}")
                    logger.info(f"Пользователь {user_id} успешно авторизован как студент ({login})")
                    send_main_menu(message.chat.id)
                    
                    conn = database.create_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE students SET telegram_id = ? WHERE name = ?", (user_id, login))
                    conn.commit()
                    conn.close()
                else:
                    bot.send_message(message.chat.id, "❌ Неверный логин или пароль.")

            del auth_states[user_id]
            
    except Exception as e:
        logger.error(f"Ошибка в handle_auth: {e}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка при авторизации.")
        if user_id in auth_states:
            del auth_states[user_id]

# ==================== ГЛАВНОЕ МЕНЮ ====================

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def handle_main_menu(call):
    send_main_menu(call.message.chat.id)
    bot.answer_callback_query(call.id)

# ==================== РАСПИСАНИЕ ====================

@bot.callback_query_handler(func=lambda call: call.data == "view_schedule")
def handle_schedule(call):
    if not is_elder(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Только старосты могут просматривать расписание.")
        return

    from datetime import datetime
    today = datetime.today().date()
    week_type = get_week_type(today)
    week_text = "*Чётная*" if week_type == "even" else "*Нечётная*"

    markup = types.InlineKeyboardMarkup()
    btn_view = types.InlineKeyboardButton("👀 Посмотреть расписание", callback_data="view_week_schedule")
    btn_next_week = types.InlineKeyboardButton("📅 Расписание след. недели", callback_data="view_next_week_schedule")
    btn_main_menu = types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    markup.add(btn_view, btn_next_week, btn_main_menu)

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📅 *Расписание*\n\nТекущая неделя: {week_text}\n\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "view_week_schedule")
def view_week_schedule(call):
    week_type = get_week_type(datetime.today().date())
    week_text = "Чётную" if week_type == "even" else "Нечётную"

    schedule = elders.get_week_schedule(week_type)
    if not schedule:
        send_main_menu_button(call.message.chat.id, "⚠️ Расписание пока не составлено.")
        return

    msg = f"📅 *Расписание на {week_text} неделю*\n\n"
    current_day = None

    for day, pair, time, subject, teacher, place in schedule:
        if day != current_day:
            if current_day is not None:
                msg += "──────────────────────────\n\n"
            msg += f" *{day}*\n"
            current_day = day

        msg += f" *{time}* — {subject or '—'}\n {teacher or '—'}\n {place or '—'}\n\n"

    message_parts = split_long_message(msg)
    
    for i, part in enumerate(message_parts):
        if i == 0:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=part,
                parse_mode="Markdown"
            )
        else:
            bot.send_message(call.message.chat.id, part, parse_mode="Markdown")
    
    # После отправки расписания отправляем кнопку главного меню
    send_main_menu_button(call.message.chat.id, "📅 Расписание загружено. Выберите дальнейшее действие:")

@bot.callback_query_handler(func=lambda call: call.data == "view_next_week_schedule")
def view_next_week_schedule(call):
    """Показывает расписание на следующую неделю"""
    from datetime import datetime, timedelta
    
    # Получаем дату через неделю
    next_week_date = datetime.today().date() + timedelta(days=7)
    week_type = get_week_type(next_week_date)
    week_text = "Чётную" if week_type == "even" else "Нечётную"

    schedule = elders.get_week_schedule(week_type)
    if not schedule:
        send_main_menu_button(call.message.chat.id, "⚠️ Расписание на следующую неделю пока не составлено.")
        return

    msg = f"📅 *Расписание на следующую неделю ({week_text})*\n\n"
    current_day = None

    for day, pair, time, subject, teacher, place in schedule:
        if day != current_day:
            if current_day is not None:
                msg += "──────────────────────────\n\n"
            msg += f" *{day}*\n"
            current_day = day

        msg += f" *{time}* — {subject or '—'}\n {teacher or '—'}\n {place or '—'}\n\n"

    message_parts = split_long_message(msg)
    
    for i, part in enumerate(message_parts):
        if i == 0:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=part,
                parse_mode="Markdown"
            )
        else:
            bot.send_message(call.message.chat.id, part, parse_mode="Markdown")
    
    # После отправки расписания отправляем кнопку главного меню
    send_main_menu_button(call.message.chat.id, "📅 Расписание на следующую неделю загружено. Выберите дальнейшее действие:")

# ==================== ТАБЕЛЬ ====================

@bot.callback_query_handler(func=lambda call: call.data == "view_grades")
def handle_grades(call):
    if not is_elder(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Только старосты могут работать с табелем.")
        return

    # Только три кнопки как в оригинале
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_add = types.InlineKeyboardButton("📝 Добавить оценку", callback_data="add_grade")
    btn_view_group = types.InlineKeyboardButton("📊 Сводка группы", callback_data="view_group_grades")
    btn_main_menu = types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    markup.add(btn_add, btn_view_group, btn_main_menu)
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="📝 Раздел *Табель* — выберите действие:",
        parse_mode="Markdown", 
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "view_group_grades")
def handle_view_group_grades(call):
    if not is_elder(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Только старосты могут просматривать сводку.")
        return

    try:
        conn = database.create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM students ORDER BY name")
        students_list = [row[0] for row in cursor.fetchall()]
        
        students_grades = {}
        for student in students_list:
            cursor.execute("SELECT subject, grade, grade_type FROM grades WHERE student_login = ? ORDER BY subject, date", (student,))
            grades = cursor.fetchall()
            subjects_dict = {}
            
            for subject, grade, grade_type in grades:
                if subject not in subjects_dict:
                    subjects_dict[subject] = []
                subjects_dict[subject].append((grade, grade_type))
            
            students_grades[student] = subjects_dict
        
        conn.close()

        if not students_grades:
            send_main_menu_button(call.message.chat.id, "📝 В группе пока нет оценок.")
            return

        msg = "📊 *Сводка по группе:*\n\n"
        for student, subjects in students_grades.items():
            msg += f"*{student}:*\n"
            
            if not subjects:
                msg += "  📝 Нет оценок\n"
            else:
                for subject, grades_list in subjects.items():
                    grades_display = []
                    total_score = 0
                    numeric_grades_count = 0
                    
                    for grade, grade_type in grades_list:
                        if grade.replace('+', '').replace('-', '').replace('.', '').isdigit():
                            try:
                                if grade.endswith('+'):
                                    total_score += float(grade[:-1]) + 0.3
                                elif grade.endswith('-'):
                                    total_score += float(grade[:-1]) - 0.3
                                else:
                                    total_score += float(grade)
                                numeric_grades_count += 1
                                grades_display.append(grade)
                            except ValueError:
                                grades_display.append(grade)
                        else:
                            grades_display.append(grade)
                    
                    total_score = round(total_score, 2)
                    grades_str = ", ".join(grades_display)
                    
                    # Показываем сумму баллов и прогресс до 21
                    progress_percentage = (total_score / 21) * 100 if 21 > 0 else 0
                    remaining_score = max(0, 21 - total_score)
                    
                    if numeric_grades_count > 0:
                        status_emoji = "🟢" if total_score >= 21 else "🟡" if progress_percentage >= 70 else "🟠" if progress_percentage >= 40 else "🔴"
                        msg += f"  {status_emoji} {subject}: {grades_str}\n"
                        msg += f"     Сумма: {total_score}/21 ({progress_percentage:.1f}%)\n"
                        if remaining_score > 0:
                            msg += f"     Осталось: {remaining_score} баллов\n"
                        else:
                            msg += f"     ✅ Цель достигнута!\n"
                    else:
                        msg += f"  📚 {subject}: {grades_str}\n"
            
            msg += "\n"

        message_parts = split_long_message(msg)

        for i, part in enumerate(message_parts):
            if i == 0:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=part,
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(call.message.chat.id, part, parse_mode="Markdown")
        
        # После отправки сводки показываем меню управления оценками
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_edit = types.InlineKeyboardButton("✏️ Изменить оценки", callback_data="edit_grades_menu")
        btn_delete_subject = types.InlineKeyboardButton("🗑️ Удалить предмет", callback_data="delete_subject_menu")
        btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="view_grades")
        markup.add(btn_edit, btn_delete_subject, btn_back)
        
        bot.send_message(
            call.message.chat.id,
            "🛠 *Управление оценками:*",
            parse_mode="Markdown",
            reply_markup=markup
        )
                
    except Exception as e:
        logger.error(f"Ошибка в handle_view_group_grades: {e}")
        bot.send_message(call.message.chat.id, "❌ Произошла ошибка при загрузке сводки.")


# ==================== РЕДАКТИРОВАНИЕ ОЦЕНОК (СТАРЫЙ ФУНКЦИОНАЛ) ====================

@bot.callback_query_handler(func=lambda call: call.data == "edit_grades_menu")
def handle_edit_grades_menu(call):
    """Меню редактирования оценок - старый функционал"""
    if not is_elder(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Только старосты могут редактировать оценки.")
        return
    
    # Получаем список студентов
    conn = database.create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM students ORDER BY name")
    students_list = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    # Сохраняем список студентов во временное хранилище
    store_temp_data(call.from_user.id, "students_list", students_list)
    
    # Создаем кнопки для выбора студента
    markup = types.InlineKeyboardMarkup(row_width=2)
    for student in students_list:
        # Используем короткий формат callback_data
        callback_data = f"egs_{student}"
        markup.add(types.InlineKeyboardButton(student, callback_data=callback_data))
    
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="view_group_grades"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="👨‍🎓 Выберите студента для изменения оценок:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("egs_"))
def handle_edit_grades_student(call):
    """Обработчик выбора студента для редактирования оценок"""
    try:
        student_name = call.data.replace("egs_", "")
        
        # Получаем список студентов из временного хранилища
        students_list = get_temp_data(call.from_user.id, "students_list")
        
        if not students_list:
            bot.answer_callback_query(call.id, "❌ Ошибка данных.")
            return
        
        # Получаем предметы студента
        subjects = grades_db.get_student_subjects(student_name)
        
        if not subjects:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="edit_grades_menu"))
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"📝 У студента *{student_name}* нет оценок.",
                parse_mode="Markdown",
                reply_markup=markup
            )
            return
        
        # Сохраняем предметы во временное хранилище
        store_temp_data(call.from_user.id, f"subjects_{student_name}", subjects)
        
        # Создаем кнопки для выбора предмета
        markup = types.InlineKeyboardMarkup(row_width=1)
        for i, subject in enumerate(subjects):
            markup.add(types.InlineKeyboardButton(
                subject, 
                callback_data=f"egsub_{student_name}_{i}"
            ))
        
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="edit_grades_menu"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📚 Выберите предмет для студента *{student_name}*:",
            parse_mode="Markdown",
            reply_markup=markup
        )
        
    except Exception as e:
        logger.error(f"Ошибка в handle_edit_grades_student: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка при загрузке предметов.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("egsub_"))
def handle_edit_grades_subject(call):
    """Обработчик выбора предмета для редактирования оценок - старый функционал"""
    try:
        parts = call.data.split("_")
        student_name = parts[1]
        subject_id = parts[2]
        
        user_id = call.from_user.id
        
        # Получаем список предметов из временного хранилища
        subjects = get_temp_data(user_id, f"subjects_{student_name}")
        
        if not subjects or int(subject_id) >= len(subjects):
            bot.answer_callback_query(call.id, "❌ Ошибка данных.")
            return
        
        subject = subjects[int(subject_id)]
        
        # Получаем все оценки студента по этому предмету
        grades = grades_db.get_student_grades_by_subject(student_name, subject)
        
        if not grades:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=f"egs_{student_name}"))
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"📝 У студента *{student_name}* нет оценок по предмету *{subject}*.",
                parse_mode="Markdown",
                reply_markup=markup
            )
            return
        
        # Формируем сообщение со списком оценок
        msg = f"📊 Оценки *{student_name}* по предмету *{subject}*:\n\n"
        
        for i, (grade_id, grade_value, grade_type, date, marked_by) in enumerate(grades, 1):
            type_emoji = {
                'practice': '🏋️',
                'seminar': '💼', 
                'exam': '📝',
                'other': '📌'
            }.get(grade_type, '📌')
            
            msg += f"{i}. {type_emoji} *{grade_value}* ({date})\n"
        
        # Создаем кнопки управления
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_add = types.InlineKeyboardButton("➕ Добавить оценку", callback_data=f"add_single_grade_{student_name}_{subject}")
        btn_add_multiple = types.InlineKeyboardButton("📝 Добавить несколько", callback_data=f"add_multiple_grades_{student_name}_{subject}")
        btn_remove = types.InlineKeyboardButton("➖ Удалить оценку", callback_data=f"remove_single_grade_{student_name}_{subject}")
        btn_remove_multiple = types.InlineKeyboardButton("🗑️ Удалить несколько", callback_data=f"remove_multiple_grades_{student_name}_{subject}")
        btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data=f"egs_{student_name}")
        
        markup.add(btn_add, btn_add_multiple, btn_remove, btn_remove_multiple, btn_back)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=msg,
            parse_mode="Markdown",
            reply_markup=markup
        )
        
    except Exception as e:
        logger.error(f"Ошибка в handle_edit_grades_subject: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка при загрузке оценок.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("remove_single_grade_"))
def handle_remove_single_grade(call):
    """Обработчик удаления одной оценки"""
    parts = call.data.split("_")
    student_name = parts[3]
    subject = parts[4]
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✏️ Введите оценку для удаления у *{student_name}* по предмету *{subject}*:",
        parse_mode="Markdown"
    )
    
    bot.register_next_step_handler(call.message, lambda msg: process_remove_single_grade(msg, student_name, subject))

def process_remove_single_grade(message, student_name, subject):
    """Обработка удаления одной оценки"""
    try:
        grade_to_remove = message.text.strip()
        
        # Получаем все оценки студента по этому предмету
        grades = grades_db.get_student_grades_by_subject(student_name, subject)
        
        if not grades:
            bot.send_message(message.chat.id, f"❌ У студента *{student_name}* нет оценок по предмету *{subject}*.")
            return
        
        # Ищем оценку для удаления
        grade_found = False
        for grade_id, grade_value, grade_type, date, marked_by in grades:
            if grade_value == grade_to_remove:
                # Удаляем оценку
                grades_db.delete_grade(grade_id)
                grade_found = True
                break
        
        if not grade_found:
            bot.send_message(message.chat.id, f"❌ У студента *{student_name}* нет оценки *{grade_to_remove}* по предмету *{subject}*.")
            return
        
        # Проверяем, остались ли еще оценки по предмету
        remaining_grades = grades_db.get_student_grades_by_subject(student_name, subject)
        
        if not remaining_grades:
            # Если оценок не осталось, удаляем предмет полностью
            grades_db.delete_subject(student_name, subject)
            bot.send_message(
                message.chat.id,
                f"✅ Оценка *{grade_to_remove}* удалена. Предмет *{subject}* удален, так как оценок не осталось.",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                message.chat.id,
                f"✅ Оценка *{grade_to_remove}* удалена у студента *{student_name}* по предмету *{subject}*.",
                parse_mode="Markdown"
            )
        
        # Вместо вызова handle_edit_grades_menu, который требует call, отправляем новое меню
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✏️ Продолжить редактирование", callback_data="edit_grades_menu"))
        markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
        
        bot.send_message(
            message.chat.id,
            "Выберите дальнейшее действие:",
            reply_markup=markup
        )
        
    except Exception as e:
        logger.error(f"Ошибка при удалении оценки: {e}")
        bot.send_message(message.chat.id, "❌ Ошибка при удалении оценки.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("remove_multiple_grades_"))
def handle_remove_multiple_grades(call):
    """Обработчик удаления нескольких оценок"""
    parts = call.data.split("_")
    student_name = parts[3]
    subject = parts[4]
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✏️ Введите оценки для удаления у *{student_name}* по предмету *{subject}*:\n\n"
             f"📝 *Формат:* через пробел, например: 5 4 3\n"
             f"ℹ️ Будут удалены только существующие оценки",
        parse_mode="Markdown"
    )
    
    bot.register_next_step_handler(call.message, lambda msg: process_remove_multiple_grades(msg, student_name, subject))

def process_remove_multiple_grades(message, student_name, subject):
    """Обработка удаления нескольких оценок"""
    try:
        grades_text = message.text.strip()
        grades_to_remove = grades_text.split()
        
        if not grades_to_remove:
            bot.send_message(message.chat.id, "❌ Не введены оценки для удаления.")
            return
        
        # Получаем все оценки студента по этому предмету
        current_grades = grades_db.get_student_grades_by_subject(student_name, subject)
        
        if not current_grades:
            bot.send_message(message.chat.id, f"❌ У студента *{student_name}* нет оценок по предмету *{subject}*.")
            return
        
        # Проверяем, есть ли все введенные оценки
        current_grade_values = [grade[1] for grade in current_grades]  # grade_value находится по индексу 1
        
        removed_count = 0
        not_found_grades = []
        
        for grade in grades_to_remove:
            if grade in current_grade_values:
                # Находим ID оценки для удаления
                for grade_id, grade_value, grade_type, date, marked_by in current_grades:
                    if grade_value == grade:
                        grades_db.delete_grade(grade_id)
                        removed_count += 1
                        break
            else:
                not_found_grades.append(grade)
        
        # Формируем сообщение о результате
        result_msg = f"📊 *Результат удаления оценок для {student_name} по {subject}:*\n\n"
        
        if removed_count > 0:
            result_msg += f"✅ Удалено оценок: *{removed_count}*\n"
        
        if not_found_grades:
            result_msg += f"❌ Не найдены оценки: *{', '.join(not_found_grades)}*\n"
        
        # Проверяем, остались ли еще оценки по предмету
        remaining_grades = grades_db.get_student_grades_by_subject(student_name, subject)
        
        if not remaining_grades:
            # Если оценок не осталось, удаляем предмет полностью
            grades_db.delete_subject(student_name, subject)
            result_msg += f"\n📝 Предмет *{subject}* удален, так как оценок не осталось."
        
        bot.send_message(message.chat.id, result_msg, parse_mode="Markdown")
        
        # Вместо вызова handle_edit_grades_menu, который требует call, отправляем новое меню
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✏️ Продолжить редактирование", callback_data="edit_grades_menu"))
        markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
        
        bot.send_message(
            message.chat.id,
            "Выберите дальнейшее действие:",
            reply_markup=markup
        )
        
    except Exception as e:
        logger.error(f"Ошибка при удалении нескольких оценок: {e}")
        bot.send_message(message.chat.id, "❌ Ошибка при удалении оценок.")

# === КОНЕЦ НОВЫХ ОБРАБОТЧИКОВ ===

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_single_grade_"))
def handle_add_single_grade(call):
    """Обработчик добавления одной оценки - старый функционал"""
    parts = call.data.split("_")
    student_name = parts[3]
    subject = parts[4]
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✏️ Введите оценку для *{student_name}* по предмету *{subject}*:",
        parse_mode="Markdown"
    )
    
    bot.register_next_step_handler(call.message, lambda msg: save_grade_value(msg, student_name, subject))


@bot.callback_query_handler(func=lambda call: call.data.startswith("add_multiple_grades_"))
def handle_add_multiple_grades(call):
    """Обработчик добавления нескольких оценок - старый функционал"""
    parts = call.data.split("_")
    student_name = parts[3]
    subject = parts[4]
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✏️ Введите оценки для *{student_name}* по предмету *{subject}*:\n\n"
             f"📝 *Формат:* через пробел, например: 5 4 3\n"
             f"ℹ️ Каждая оценка будет добавлена отдельно",
        parse_mode="Markdown"
    )
    
    bot.register_next_step_handler(call.message, lambda msg: process_add_multiple_grades(msg, student_name, subject))

def process_add_multiple_grades(message, student_name, subject):
    """Обработка добавления нескольких оценок - старый функционал"""
    try:
        grades_text = message.text.strip()
        grades_list = grades_text.split()
        
        if not grades_list:
            bot.send_message(message.chat.id, "❌ Не введены оценки.")
            return
        
        # Получаем информацию о старосте
        user_id = message.from_user.id
        elder_info = elders.get_elder_info(user_id)
        if not elder_info:
            bot.send_message(message.chat.id, "❌ Ошибка авторизации.")
            return
        
        elder_login = elder_info[0]
        
        # Сохраняем каждую оценку
        from datetime import date
        today = date.today().isoformat()
        added_count = 0
        for grade in grades_list:
            grades_db.add_grade(
                student_login=student_name,
                subject=subject,
                grade=grade.strip(),
                grade_type="other",  # тип по умолчанию
                marked_by=elder_login,
                date=today
            )
            added_count += 1
        
        bot.send_message(
            message.chat.id,
            f"✅ Добавлено {added_count} оценок для *{student_name}* по предмету *{subject}*",
            parse_mode="Markdown"
        )
        
        # Возвращаем к меню редактирования
        handle_edit_grades_menu(message)
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении нескольких оценок: {e}")
        bot.send_message(message.chat.id, "❌ Ошибка при добавлении оценок.")



# ==================== УДАЛЕНИЕ ПРЕДМЕТОВ (СТАРЫЙ ФУНКЦИОНАЛ) ====================

@bot.callback_query_handler(func=lambda call: call.data == "delete_subject_menu")
def handle_delete_subject_menu(call):
    """Меню удаления предметов - старый функционал"""
    if not is_elder(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Только старосты могут удалять предметы.")
        return
    
    # Получаем список студентов
    conn = database.create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM students ORDER BY name")
    students_list = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    # Создаем кнопки для выбора студента
    markup = types.InlineKeyboardMarkup(row_width=2)
    for student in students_list:
        markup.add(types.InlineKeyboardButton(student, callback_data=f"delete_subject_student_{student}"))
    
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="view_group_grades"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="👨‍🎓 Выберите студента для удаления предмета:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_subject_student_"))
def handle_delete_subject_student(call):
    """Обработчик выбора студента для удаления предмета - старый функционал"""
    student_name = call.data.replace("delete_subject_student_", "")
    
    # Получаем предметы студента
    subjects = grades_db.get_student_subjects(student_name)
    
    if not subjects:
        bot.answer_callback_query(call.id, f"❌ У студента {student_name} нет оценок.")
        return
    
    # Создаем кнопки для выбора предмета
    markup = types.InlineKeyboardMarkup(row_width=1)
    for subject in subjects:
        markup.add(types.InlineKeyboardButton(subject, callback_data=f"confirm_delete_subject_{student_name}_{subject}"))
    
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="delete_subject_menu"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📚 Выберите предмет для удаления у студента *{student_name}*:",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_delete_subject_"))
def handle_confirm_delete_subject(call):
    """Подтверждение удаления предмета - старый функционал"""
    parts = call.data.split("_")
    student_name = parts[3]
    subject = parts[4]
    
    # Создаем кнопки подтверждения
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_confirm = types.InlineKeyboardButton("✅ Да, удалить", callback_data=f"final_delete_subject_{student_name}_{subject}")
    btn_cancel = types.InlineKeyboardButton("❌ Отмена", callback_data=f"delete_subject_student_{student_name}")
    
    markup.add(btn_confirm, btn_cancel)
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"⚠️ *Внимание!* Вы уверены, что хотите удалить *ВСЕ* оценки по предмету *{subject}* у студента *{student_name}*?\n\n"
             f"❌ *Это действие нельзя отменить!*",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("final_delete_subject_"))
def handle_final_delete_subject(call):
    """Финальное удаление предмета - старый функционал"""
    parts = call.data.split("_")
    student_name = parts[3]
    subject = parts[4]
    
    # Удаляем все оценки по предмету
    grades_db.delete_subject(student_name, subject)
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ Все оценки по предмету *{subject}* у студента *{student_name}* удалены!",
        parse_mode="Markdown"
    )
    
    # Возвращаем в меню через 2 секунды
    time.sleep(2)
    handle_view_group_grades(call)

# ==================== ОБРАБОТЧИКИ ДЛЯ ТАБЕЛЯ ====================

@bot.callback_query_handler(func=lambda call: call.data == "add_grade")
def handle_add_grade(call):
    if not is_elder(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Только старосты могут добавлять оценки.")
        return
    
    conn = database.create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM students WHERE group_name = 'СПД-103' ORDER BY name")
    students_list = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    if not students_list:
        bot.answer_callback_query(call.id, "❌ В группе нет студентов.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for student in students_list:
        markup.add(types.InlineKeyboardButton(student, callback_data=f"grade_student_{student}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="view_grades"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="👨‍🎓 Выберите студента для добавления оценки:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("grade_student_"))
def handle_grade_student_selection(call):
    student_name = call.data.replace("grade_student_", "")
    
    existing_subjects = grades_db.get_student_subjects(student_name)
    
    if existing_subjects:
        message_text = f"📚 Выберите предмет для *{student_name}* или введите новый:"
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        for subject in existing_subjects:
            markup.add(types.InlineKeyboardButton(
                f"📖 {subject}", 
                callback_data=f"existing_subject_{student_name}_{subject}"
            ))
        
        markup.add(types.InlineKeyboardButton("➕ Новый предмет", callback_data=f"new_subject_{student_name}"))
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="add_grade"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=message_text,
            parse_mode="Markdown",
            reply_markup=markup
        )
    else:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✏️ Введите предмет для *{student_name}*:",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(call.message, lambda msg: save_grade_subject(msg, student_name))

def save_grade_subject(message, student_name):
    subject = message.text.strip()
    bot.send_message(
        message.chat.id,
        f"📚 Предмет: *{subject}*\n\nТеперь введите оценку (можно цифры, буквы, '+', '-'):",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(message, lambda msg: save_grade_value(msg, student_name, subject))

def save_grade_value(message, student_name, subject):
    grade = message.text.strip()
    
    user_id = message.from_user.id
    if user_id not in temp_storage:
        temp_storage[user_id] = {}
    temp_storage[user_id]["current_grade"] = {
        'student_name': student_name,
        'subject': subject,
        'grade': grade
    }
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_practice = types.InlineKeyboardButton("🏋️ Практика", callback_data="gt_practice")
    btn_seminar = types.InlineKeyboardButton("💼 Семинар", callback_data="gt_seminar")
    btn_exam = types.InlineKeyboardButton("📝 Экзамен", callback_data="gt_exam")
    btn_other = types.InlineKeyboardButton("📌 Другое", callback_data="gt_other")
    markup.add(btn_practice, btn_seminar, btn_exam, btn_other)
    
    bot.send_message(
        message.chat.id,
        f"📊 Выберите тип занятия для оценки *{grade}* по предмету *{subject}*:",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("existing_subject_"))
def handle_existing_subject(call):
    parts = call.data.split("_")
    student_name = parts[2]
    subject = parts[3]
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📚 Предмет: *{subject}*\n\nТеперь введите оценку для *{student_name}* (можно цифры, буквы, '+', '-'):",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(call.message, lambda msg: save_grade_value(msg, student_name, subject))

@bot.callback_query_handler(func=lambda call: call.data.startswith("new_subject_"))
def handle_new_subject(call):
    student_name = call.data.replace("new_subject_", "")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✏️ Введите новый предмет для *{student_name}*:",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(call.message, lambda msg: save_grade_subject(msg, student_name))

@bot.callback_query_handler(func=lambda call: call.data in ["gt_practice", "gt_seminar", "gt_exam", "gt_other"])
def handle_grade_type_selection(call):
    user_id = call.from_user.id
    if user_id not in temp_storage or "current_grade" not in temp_storage[user_id]:
        bot.answer_callback_query(call.id, "❌ Ошибка: данные не найдены.")
        return
    
    grade_data = temp_storage[user_id]["current_grade"]
    student_name = grade_data['student_name']
    subject = grade_data['subject']
    grade = grade_data['grade']
    
    grade_type = {
        "gt_practice": "practice",
        "gt_seminar": "seminar",
        "gt_exam": "exam",
        "gt_other": "other"
    }[call.data]
    
    elder_info = elders.get_elder_info(user_id)
    if not elder_info:
        bot.answer_callback_query(call.id, "❌ Ошибка авторизации.")
        return
    
    marked_by = elder_info[0]
    
    # Добавляем дату
    from datetime import date
    today = date.today().isoformat()
    
    grades_db.add_grade(student_name, subject, grade, grade_type, marked_by, today)
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ Оценка *{grade}* по предмету *{subject}* для *{student_name}* успешно добавлена!",
        parse_mode="Markdown"
    )
    
    del temp_storage[user_id]["current_grade"]
    
    # Возвращаем в меню табеля
    handle_grades(call)

# ==================== ПРОПУСКИ ====================

@bot.callback_query_handler(func=lambda call: call.data == "view_attendance")
def handle_attendance(call):
    if not is_elder(call.from_user.id):
        # Студент - только просмотр своих пропусков
        student_info = students.get_student_info(call.from_user.id)
        if not student_info:
            bot.answer_callback_query(call.id, "❌ Ошибка авторизации.")
            return
            
        login = student_info[0]
        total_hours = attendance_db.get_student_total_hours(login)
        remaining = max(0, 20 - total_hours)

        msg = f"📊 *Ваша статистика пропусков:*\n\nВы пропустили: *{total_hours} ч.* из 20 допустимых.\n⏳ Осталось: *{remaining} ч.*\n\n"
        
        if total_hours >= 20:
            msg += "⚠️ *Внимание:* лимит пропусков превышен!"
        elif total_hours >= 15:
            msg += "❗ *Предупреждение:* вы близки к лимиту пропусков."
        else:
            msg += "✅ Всё в порядке."

        send_main_menu_button(call.message.chat.id, msg)
        return

    # Староста - полный доступ
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_add = types.InlineKeyboardButton("📋 Отметить пропуск", callback_data="add_absence")
    btn_view = types.InlineKeyboardButton("📊 Посмотреть сводку", callback_data="view_absence_summary")
    btn_main_menu = types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    markup.add(btn_add, btn_view, btn_main_menu)
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="🚫 Раздел *Пропуски* — выберите действие:",
        parse_mode="Markdown", 
        reply_markup=markup
    )

# ==================== ПРИОРИТЕТЫ ====================

# ==================== ПРИОРИТЕТЫ (ИСПРАВЛЕННАЯ ВЕРСИЯ) ====================

@bot.callback_query_handler(func=lambda call: call.data == "view_priority")
def handle_priority(call):
    if not is_elder(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Только старосты могут работать с приоритетами.")
        return
    
    # Получаем список предметов, по которым есть оценки
    subjects = grades_db.get_all_subjects()
    if not subjects:
        send_main_menu_button(call.message.chat.id, "📚 Нет предметов с оценками для анализа приоритетов.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for subject in subjects:
        markup.add(types.InlineKeyboardButton(subject, callback_data=f"pri_sub_{subject}"))
    markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="📚 Выберите предмет для анализа приоритетов:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("pri_sub_"))
def handle_priority_subject_detail(call):
    """Показывает детальную статистику по студентам для выбранного предмета"""
    subject = call.data.replace("pri_sub_", "")
    
    try:
        # Получаем всех студентов
        conn = database.create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM students ORDER BY name")
        students_list = [row[0] for row in cursor.fetchall()]
        
        student_stats = []
        
        for student_name in students_list:
            # Получаем оценки по предмету
            cursor.execute("""
                SELECT grade, grade_type, date 
                FROM grades 
                WHERE student_login = ? AND subject = ?
                ORDER BY date
            """, (student_name, subject))
            grades = cursor.fetchall()
            
            # Получаем пропуски
            cursor.execute("""
                SELECT SUM(hours) 
                FROM attendance 
                WHERE student_login = ?
            """, (student_name,))
            absence_result = cursor.fetchone()
            absence_hours = absence_result[0] if absence_result[0] is not None else 0
            
            # Считаем СУММУ баллов вместо среднего
            grade_count = len(grades)
            grades_list = [grade[0] for grade in grades]
            
            # Вычисляем сумму баллов (только для числовых оценок)
            total_score = 0
            numeric_grades_count = 0
            
            for grade in grades_list:
                if grade.replace('+', '').replace('-', '').replace('.', '').isdigit():
                    try:
                        if grade.endswith('+'):
                            total_score += float(grade[:-1]) + 0.3
                        elif grade.endswith('-'):
                            total_score += float(grade[:-1]) - 0.3
                        else:
                            total_score += float(grade)
                        numeric_grades_count += 1
                    except ValueError:
                        continue
            
            # Округляем до 2 знаков после запятой
            total_score = round(total_score, 2)
            
            # Определяем статус студента
            progress_percentage = (total_score / 21) * 100 if 21 > 0 else 0
            remaining_score = max(0, 21 - total_score)
            
            student_stats.append({
                'name': student_name,
                'grade_count': grade_count,
                'grades': grades_list,
                'total_score': total_score,
                'remaining_score': remaining_score,
                'progress_percentage': progress_percentage,
                'absence_hours': absence_hours,
                'numeric_grades_count': numeric_grades_count
            })
        
        conn.close()
        
        # Сортируем студентов по оставшимся баллам (от большего к меньшему) - кто больше всего отстает
        student_stats.sort(key=lambda x: x['remaining_score'], reverse=True)
        
        # Формируем сообщение
        msg = f"📊 *Статистика по предмету: {subject}*\n"
        msg += f"🎯 *Цель: 21 балл для допуска к сессии*\n\n"
        
        for i, student in enumerate(student_stats, 1):
            # Определяем эмодзи статуса
            if student['total_score'] >= 21:
                status_emoji = "🟢"  # Достигнута цель
                status_text = "ЦЕЛЬ ДОСТИГНУТА"
            elif student['progress_percentage'] >= 70:
                status_emoji = "🟡"  # Хороший прогресс
                status_text = "ХОРОШИЙ ПРОГРЕСС"
            elif student['progress_percentage'] >= 40:
                status_emoji = "🟠"  # Средний прогресс
                status_text = "СРЕДНИЙ ПРОГРЕСС"
            else:
                status_emoji = "🔴"  # Низкий прогресс
                status_text = "НИЗКИЙ ПРОГРЕСС"
            
            msg += f"{status_emoji} *{student['name']}* ({status_text})\n"
            msg += f"   📝 Оценок: {student['grade_count']}\n"
            msg += f"   Оценки: {', '.join(student['grades']) if student['grades'] else '—'}\n"
            msg += f"   Сумма баллов: {student['total_score']}/21\n"
            msg += f"   Прогресс: {student['progress_percentage']:.1f}%\n"
            
            if student['remaining_score'] > 0:
                msg += f"   ⚠️ Осталось набрать: {student['remaining_score']} баллов\n"
            else:
                msg += f"   ✅ Цель достигнута!\n"
                
            msg += f"   ⏰ Пропусков: {student['absence_hours']}ч.\n\n"
        
        # Добавляем сводку по группе
        students_with_goal = len([s for s in student_stats if s['total_score'] >= 21])
        total_students = len(student_stats)
        goal_percentage = (students_with_goal / total_students) * 100 if total_students > 0 else 0
        
        msg += f"📋 *Сводка по группе:*\n"
        msg += f"✅ Достигли цели: {students_with_goal}/{total_students} ({goal_percentage:.1f}%)\n"
        msg += f"Средний прогресс: {sum(s['progress_percentage'] for s in student_stats) / len(student_stats):.1f}%\n\n"
        
        # Добавляем легенду
        msg += "📋 *Легенда:*\n"
        msg += "🟢 — Цель достигнута (21+ баллов)\n"
        msg += "🟡 — Хороший прогресс (70-99%)\n"
        msg += "🟠 — Средний прогресс (40-69%)\n"
        msg += "🔴 — Низкий прогресс (0-39%)\n"
        
        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("🔙 К списку предметов", callback_data="view_priority")
        btn_main = types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        markup.add(btn_back, btn_main)
        
        # Разбиваем длинное сообщение на части
        message_parts = split_long_message(msg)
        
        for i, part in enumerate(message_parts):
            if i == 0:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=part,
                    parse_mode="Markdown",
                    reply_markup=markup if i == len(message_parts) - 1 else None
                )
            else:
                if i == len(message_parts) - 1:
                    bot.send_message(call.message.chat.id, part, parse_mode="Markdown", reply_markup=markup)
                else:
                    bot.send_message(call.message.chat.id, part, parse_mode="Markdown")
                    
    except Exception as e:
        logger.error(f"Ошибка в handle_priority_subject_detail: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка при загрузке статистики.")

# ==================== ОБРАБОТЧИКИ ДЛЯ ПРОПУСКОВ ====================

@bot.callback_query_handler(func=lambda call: call.data == "add_absence")
def handle_add_absence(call):
    if not is_elder(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Только старосты могут отмечать пропуски.")
        return
    
    conn = database.create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM students")
    students_list = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for student in students_list:
        markup.add(types.InlineKeyboardButton(student, callback_data=f"absence_student_{student}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="view_attendance"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="👨‍🎓 Выберите студента для отметки пропуска:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("absence_student_"))
def handle_absence_student_selection(call):
    student_name = call.data.replace("absence_student_", "")
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✏️ Введите количество часов пропуска для *{student_name}* (от 1 до 8):",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(call.message, lambda msg: save_absence_hours(msg, student_name))

def save_absence_hours(message, student_name):
    try:
        hours = int(message.text)
        if hours < 1 or hours > 8:
            raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ Введите корректное число часов (1–8).")
        return
    
    elder_info = elders.get_elder_info(message.from_user.id)
    if not elder_info:
        bot.send_message(message.chat.id, "❌ Ошибка авторизации.")
        return
    
    elder_login = elder_info[0]
    
    from datetime import date
    attendance_db.add_absence(
        student_login=student_name,
        subject="Не указано",
        hours=hours,
        reason="Не указана",
        marked_by=elder_login,
        date=date.today().isoformat()
    )
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_summary = types.InlineKeyboardButton("📊 Посмотреть сводку", callback_data="view_absence_summary")
    btn_main_menu = types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    markup.add(btn_summary, btn_main_menu)
    
    bot.send_message(
        message.chat.id,
        f"✅ Пропуск для *{student_name}* на *{hours}* ч. успешно добавлен.\n\nВыберите дальнейшее действие:",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "view_absence_summary")
def handle_view_absence_summary(call):
    if not is_elder(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Только старосты могут просматривать сводку.")
        return
    
    conn = database.create_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.name, COALESCE(SUM(a.hours), 0) as total_hours
        FROM students s
        LEFT JOIN attendance a ON s.name = a.student_login
        GROUP BY s.name
        ORDER BY s.name
    """)
    students_data = cursor.fetchall()
    conn.close()
    
    msg = "📊 *Сводка по пропускам:*\n\n"
    for student_name, total_hours in students_data:
        remaining = max(0, 20 - total_hours)
        status = "✅" if total_hours < 15 else "⚠️" if total_hours < 20 else "❌"
        msg += f"{status} *{student_name}:* {total_hours}ч. (осталось: {remaining}ч.)\n"
    
    # ОБНОВЛЕННЫЙ БЛОК С КНОПКАМИ
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_add = types.InlineKeyboardButton("➕ Добавить пропуск", callback_data="add_absence")
    btn_remove = types.InlineKeyboardButton("➖ Убрать пропуск", callback_data="remove_absence_menu")
    btn_reset = types.InlineKeyboardButton("🔄 Сбросить пропуски", callback_data="confirm_reset_absences")
    btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="view_attendance")
    markup.add(btn_add, btn_remove, btn_reset, btn_back)
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=msg,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "remove_absence_menu")
def handle_remove_absence_menu(call):
    """Меню удаления пропусков"""
    if not is_elder(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Только старосты могут убирать пропуски.")
        return
    
    conn = database.create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM students")
    students_list = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for student in students_list:
        markup.add(types.InlineKeyboardButton(student, callback_data=f"remove_absence_student_{student}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="view_absence_summary"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="👨‍🎓 Выберите студента для удаления пропусков:",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("remove_absence_student_"))
def handle_remove_absence_student(call):
    """Обработчик выбора студента для удаления пропусков"""
    student_name = call.data.replace("remove_absence_student_", "")
    
    # Получаем текущие пропуски студента
    total_hours = attendance_db.get_student_total_hours(student_name)
    
    if total_hours == 0:
        bot.answer_callback_query(call.id, f"❌ У {student_name} нет пропусков.")
        return
    
    # Ограничиваем максимальное количество часов для удаления
    max_hours_to_remove = min(total_hours, 31)  # Не больше 31 часа за раз
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        # УБИРАЕМ Markdown разметку
        text=f"✏️ У {student_name} текущие пропуски: {total_hours}ч.\n\n"
             f"Введите количество часов для удаления (от 1 до {max_hours_to_remove}):"
    )
    bot.register_next_step_handler(call.message, lambda msg: process_remove_absence_hours(msg, student_name))

def process_remove_absence_hours(message, student_name):
    """Обработка удаления часов пропусков"""
    try:
        # Проверяем, что введено число
        hours_to_remove = int(message.text)
        total_hours = attendance_db.get_student_total_hours(student_name)
        
        if total_hours == 0:
            bot.send_message(message.chat.id, f"❌ У {student_name} нет пропусков.")
            return
            
        if hours_to_remove < 1:
            bot.send_message(message.chat.id, "⚠️ Введите число больше 0.")
            return
            
        if hours_to_remove > total_hours:
            bot.send_message(message.chat.id, f"⚠️ Нельзя удалить больше {total_hours}ч. (текущие пропуски студента).")
            return
        
        # Удаляем часы
        removed_count = attendance_db.remove_absence(student_name, hours_to_remove)
        
        if removed_count > 0:
            new_total = attendance_db.get_student_total_hours(student_name)
            # УБИРАЕМ Markdown разметку чтобы избежать ошибок
            bot.send_message(
                message.chat.id,
                f"✅ Убрано {removed_count}ч. пропусков у {student_name}\n"
                f"📊 Теперь пропусков: {new_total}ч."
            )
            
            # Создаем кнопки для навигации
            markup = types.InlineKeyboardMarkup(row_width=1)
            btn_back = types.InlineKeyboardButton("📊 Вернуться к сводке", callback_data="view_absence_summary")
            btn_main = types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
            markup.add(btn_back, btn_main)
            
            bot.send_message(
                message.chat.id,
                "Выберите дальнейшее действие:",
                reply_markup=markup
            )
        else:
            bot.send_message(
                message.chat.id,
                f"❌ Не удалось убрать пропуски у {student_name}. Возможно, произошла ошибка в базе данных."
            )
        
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ Пожалуйста, введите корректное число.")
    except Exception as e:
        logger.error(f"Ошибка при удалении пропусков: {e}")
        bot.send_message(
            message.chat.id,
            f"❌ Произошла ошибка при удалении пропусков"
        )

@bot.callback_query_handler(func=lambda call: call.data == "confirm_reset_absences")
def handle_confirm_reset_absences(call):
    """Подтверждение сброса всех пропусков"""
    if not is_elder(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Только старосты могут сбрасывать пропуски.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_confirm = types.InlineKeyboardButton("✅ Да, сбросить", callback_data="reset_absences")
    btn_cancel = types.InlineKeyboardButton("❌ Отмена", callback_data="view_absence_summary")
    markup.add(btn_confirm, btn_cancel)
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="⚠️ *ВНИМАНИЕ!*\n\n"
             "Вы уверены, что хотите сбросить пропуски у *ВСЕЙ* группы?\n\n"
             "❌ *Это действие нельзя отменить!*\n"
             "📊 Все данные о пропусках будут удалены.",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "reset_absences")
def handle_reset_absences(call):
    """Финальный сброс всех пропусков"""
    if not is_elder(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Только старосты могут сбрасывать пропуски.")
        return
    
    try:
        # Показываем сообщение о начале процесса
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🔄 Сбрасываю пропуски... Это может занять несколько секунд."
        )
        
        # Выполняем сброс
        success = attendance_db.reset_all_absences()
        
        if success:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                # УБИРАЕМ Markdown разметку
                text="✅ Все пропуски успешно сброшены!\n\n"
                     "📊 Теперь у всех студентов 0 часов пропусков."
            )
            
            # Создаем кнопки для навигации
            markup = types.InlineKeyboardMarkup(row_width=1)
            btn_back = types.InlineKeyboardButton("📊 Вернуться к сводке", callback_data="view_absence_summary")
            btn_main = types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
            markup.add(btn_back, btn_main)
            
            # Отправляем новое сообщение с кнопками
            bot.send_message(
                call.message.chat.id,
                "Выберите дальнейшее действие:",
                reply_markup=markup
            )
        else:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                # УБИРАЕМ Markdown разметку
                text="❌ Не удалось сбросить пропуски!\n\n"
                     "Пожалуйста, попробуйте позже или проверьте базу данных."
            )
            
    except Exception as e:
        logger.error(f"Ошибка при сбросе пропусков: {e}")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            # УБИРАЕМ Markdown разметку
            text=f"❌ Произошла ошибка при сбросе пропусков!\n\nОшибка: {str(e)}"
        )

# ==================== ОБРАБОТЧИКИ ДЛЯ ПРИОРИТЕТОВ ====================

@bot.callback_query_handler(func=lambda call: call.data.startswith("pri_sub_"))
def handle_priority_subject(call):
    subject = call.data.replace("pri_sub_", "")
    
    priority_team, fire_team, reserve_team = priority_db.calculate_priority_teams(subject)
    priority_db.save_priority_teams(subject, priority_team, fire_team, reserve_team)
    
    msg = f"🎯 *Приоритетные команды по предмету: {subject}*\n\n"
    
    msg += "🔴 *1. ПРИОРИТЕТ* (мало оценок + много пропусков / низкий балл):\n"
    if priority_team:
        for student in priority_team:
            msg += f"   • {student['name']} (оценок: {student['grade_count']}, пропусков: {student['absence_hours']}ч, ср. балл: {student['avg_grade']})\n"
    else:
        msg += "   — нет студентов\n"
    msg += "\n"
    
    msg += "🟡 *2. ПОЖАРНААЯ КОМАНДА* (средние показатели):\n"
    if fire_team:
        for student in fire_team:
            msg += f"   • {student['name']} (оценок: {student['grade_count']}, пропусков: {student['absence_hours']}ч, ср. балл: {student['avg_grade']})\n"
    else:
        msg += "   — нет студентов\n"
    msg += "\n"
    
    msg += "🟢 *3. ЗАПАС* (отличные показатели):\n"
    if reserve_team:
        for student in reserve_team:
            msg += f"   • {student['name']} (оценок: {student['grade_count']}, пропусков: {student['absence_hours']}ч, ср. балл: {student['avg_grade']})\n"
    else:
        msg += "   — нет студентов\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=msg,
        parse_mode="Markdown",
        reply_markup=markup
    )

# ==================== ПРОВЕРКА БАЗЫ ДАННЫХ ====================

def check_attendance_db():
    """Проверяет состояние базы данных пропусков"""
    try:
        conn = database.create_connection()
        cursor = conn.cursor()
        
        # Проверяем существование таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attendance'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("❌ Таблица 'attendance' не существует!")
            return False
            
        # Проверяем структуру таблицы
        cursor.execute("PRAGMA table_info(attendance)")
        columns = cursor.fetchall()
        print("Структура таблицы attendance:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
            
        # Проверяем количество записей
        cursor.execute("SELECT COUNT(*) FROM attendance")
        count = cursor.fetchone()[0]
        print(f"Количество записей в attendance: {count}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Ошибка при проверке базы данных: {e}")
        return False

# ==================== ЗАПУСК БОТА ====================

if __name__ == "__main__":
    # Проверяем базу данных перед запуском
    print("🔍 Проверка базы данных пропусков...")
    check_attendance_db()
    
    logger.info("Бот запущен и готов к работе.")
    while True:
        try:
            bot.polling(none_stop=True, interval=1)
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            time.sleep(5)