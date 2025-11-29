import os
import logging
from datetime import datetime
import telebot
import attendance_db
from telebot import types
import students
import grades_db
import database
from config import STUDENT_BOT_TOKEN 
from database import fill_sample_schedule


auth_states = {}  # для процесса авторизации (ввод логина/пароля)
student_sessions = {}  # для хранения текущих сессий после авторизации
bot = telebot.TeleBot(STUDENT_BOT_TOKEN)



# Тихая инициализация базы данных расписания
database.init_schedule_db()
database.fill_sample_schedule()  # Заполняем только если таблица пустая

# Настройка логирования
today_date = datetime.now().strftime("%Y-%m-%d")


# Настройка логирования (аналогично основному боту)
today_date = datetime.now().strftime("%Y-%m-%d")

log_folder = "student_logs"
if not os.path.exists(log_folder):
    os.makedirs(log_folder)
    print(f"📁 Папка '{log_folder}' создана.")

log_file = os.path.join(log_folder, f"student_logs_{today_date}.txt")

# ⚙️ Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format=u'%(filename)20s [LINE:%(lineno)-4s] %(levelname)-8s [%(asctime)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8', mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


logger.info("Бот для абитуриентов запущен и готов к работе.")

def check_schedule_days():
    """
    Проверить, какие дни есть в расписании
    """
    conn = create_connection()
    if conn is not None:
        try:
            cursor = conn.cursor()
            
            # Проверяем четную неделю
            cursor.execute("SELECT DISTINCT day FROM schedule WHERE week_type = 'even'")
            even_days = cursor.fetchall()
            print("Дни в четной неделе:", [day[0] for day in even_days])
            
            # Проверяем нечетную неделю
            cursor.execute("SELECT DISTINCT day FROM schedule WHERE week_type = 'odd'")
            odd_days = cursor.fetchall()
            print("Дни в нечетной неделе:", [day[0] for day in odd_days])
            
        except Exception as e:
            print(f"Ошибка при проверке дней: {e}")
        finally:
            conn.close()

def get_current_student_login(user_id):
    """
    Получить текущий логин студента из сессии
    """
    if user_id in student_sessions:
        return student_sessions[user_id]["current_login"]
    return None

def send_student_main_menu(chat_id):
    """
    Главное меню для абитуриентов
    """
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    btn_schedule = types.InlineKeyboardButton(
        text="📅 Расписание", 
        callback_data="student_view_schedule"
    )
    btn_grades = types.InlineKeyboardButton(
        text="📊 Табель", 
        callback_data="student_view_grades"
    )
    btn_priority = types.InlineKeyboardButton(
        text="🎯 Приоритеты",
        callback_data="student_view_priority"
    )
    
    markup.add(btn_schedule, btn_grades, btn_priority)
    
    bot.send_message(chat_id, "Выберите нужный функционал:", reply_markup=markup)




# Обработчик главного меню
@bot.callback_query_handler(func=lambda call: call.data == "student_main_menu")
def handle_student_main_menu(call):
    send_student_main_menu(call.message.chat.id)  # Убрали bot из аргументов
    bot.answer_callback_query(call.id)


# Стартовая функция
@bot.message_handler(commands=['start'])
def start_message(message):
    logger.info(f"Абитуриент {message.from_user.id} вызвал /start")

    text = (
        "👋 Привет, абитуриент!\n\n"
        "Этот бот поможет тебе следить за расписанием, оценками "
        "и учебными приоритетами.\n\n"
        "Выбери свою группу:"
    )

    markup = types.InlineKeyboardMarkup()
    btn_group = types.InlineKeyboardButton(text="СПД-103", callback_data="student_group_SPD103")
    markup.add(btn_group)
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(commands=['logout'])
def handle_logout(message):
    user_id = message.from_user.id
    if user_id in student_sessions:
        login = student_sessions[user_id]["current_login"]
        del student_sessions[user_id]
        bot.send_message(message.chat.id, f"✅ Вы вышли из аккаунта {login}")
        logger.info(f"Студент {login} вышел из системы")
    else:
        bot.send_message(message.chat.id, "❌ Вы не авторизованы")


# Обработчик выбора группы
@bot.callback_query_handler(func=lambda call: call.data == "student_group_SPD103")
def handle_student_group(call):
    logger.info(f"Абитуриент {call.from_user.id} выбрал группу СПД-103")
    bot.answer_callback_query(call.id)

    text = "✅ Группа СПД-103 выбрана!\n\nДля доступа к функциям бота требуется авторизация."

    markup = types.InlineKeyboardMarkup()
    btn_student = types.InlineKeyboardButton("🎓 Авторизация абитуриента", callback_data="student_role_student")
    markup.add(btn_student)

    bot.send_message(call.message.chat.id, text, reply_markup=markup)

# Обработчик выбора роли
@bot.callback_query_handler(func=lambda call: call.data == "student_role_student")
def handle_student_role(call):
    logger.info(f"Пользователь {call.from_user.id} выбрал роль: Абитуриент")
    bot.answer_callback_query(call.id)
    
    auth_states[call.from_user.id] = {"step": "login_student", "login": None}
    bot.send_message(call.message.chat.id, "🎓 Авторизация абитуриента.\nВведите ваш логин:")

# Обработчик авторизации
@bot.message_handler(func=lambda message: message.from_user.id in auth_states)
def handle_auth(message):
    user_id = message.from_user.id
    state = auth_states[user_id]

    if state["step"] == "login_student":
        state["login"] = message.text.strip()
        state["step"] = "password_student"
        bot.send_message(message.chat.id, "Введите пароль:")
        logger.info(f"Абитуриент {user_id} ввел логин: {state['login']}")

    elif state["step"] == "password_student":
        login = state["login"]
        password = message.text.strip()

        conn = database.create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, password_hash, group_name FROM students WHERE name = ?", (login,))
        row = cursor.fetchone()
        conn.close()

        if row and database.hash_password(password) == row[1]:
            current_name, password_hash, group_name = row
            
            logger.info(f"DEBUG: Успешная авторизация для {login}")
            
            # СОХРАНЯЕМ ТЕКУЩУЮ СЕССИЮ
            student_sessions[user_id] = {"current_login": login}
            
            bot.send_message(
                message.chat.id,
                f"✅ Авторизация успешна! Добро пожаловать, {login}.\nВаша группа: {group_name}"
            )
            logger.info(f"Абитуриент {user_id} успешно авторизован как {login}")
            
            send_student_main_menu(message.chat.id)
        else:
            bot.send_message(message.chat.id, "❌ Неверный логин или пароль. Попробуйте ещё раз.")
            logger.warning(f"Неудачная попытка авторизации абитуриента: {user_id} / {login}")

        del auth_states[user_id]


@bot.callback_query_handler(func=lambda call: call.data == "student_view_grades")
def handle_student_grades(call):
    user_id = call.from_user.id
    current_login = get_current_student_login(user_id)

    # ОТЛАДОЧНАЯ ИНФОРМАЦИЯ
    logger.info(f"DEBUG: user_id={user_id}, current_login={current_login}")
    
    if not current_login:
        bot.answer_callback_query(call.id, "❌ Ошибка авторизации. Войдите заново.")
        logger.warning(f"Пользователь {user_id} не авторизован")
        return

    student_info = students.get_student_info(current_login)
    
    if not student_info:
        bot.answer_callback_query(call.id, "❌ Ошибка авторизации.")
        return

    login = student_info[0]
    logger.info(f"Студент {login} запросил свой табель")
    
    try:
        # Получаем оценки для ЭТОГО конкретного студента
        grades = grades_db.get_student_grades(login)
        
        # Получаем пропуски для ЭТОГО конкретного студента
        total_hours = attendance_db.get_student_total_hours(login)
        remaining_hours = max(0, 20 - total_hours)
        
        # Формируем сообщение
        msg = "📊 *Ваш табель успеваемости*\n\n"
        
        # Раздел с оценками
        if grades:
            subjects_grades = {}
            for subject, grade, grade_type, date, marked_by in grades:
                if subject not in subjects_grades:
                    subjects_grades[subject] = []
                subjects_grades[subject].append((grade, grade_type, date))
            
            msg += "*Оценки:*\n"
            for subject, grade_list in subjects_grades.items():
                msg += f"📚 *{subject}:*\n"
                
                # Считаем сумму баллов для этого предмета
                total_score = 0
                numeric_grades_count = 0
                
                for grade, grade_type, date in grade_list:
                    type_emoji = "🏋️" if grade_type == "practice" else "💼" if grade_type == "seminar" else "📝" if grade_type == "exam" else "📌"
                    msg += f"  {type_emoji} {grade} ({date})\n"
                    
                    # Считаем сумму для числовых оценок
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
                
                # Показываем сумму баллов и прогресс до 21
                total_score = round(total_score, 2)
                progress_percentage = (total_score / 21) * 100 if 21 > 0 else 0
                remaining_score = max(0, 21 - total_score)
                
                if numeric_grades_count > 0:
                    status_emoji = "🟢" if total_score >= 21 else "🟡" if progress_percentage >= 70 else "🟠" if progress_percentage >= 40 else "🔴"
                    msg += f"  {status_emoji} *Сумма баллов: {total_score}/21* ({progress_percentage:.1f}%)\n"
                    
                    if remaining_score > 0:
                        msg += f"  ⚠️ *Осталось набрать: {remaining_score} баллов*\n"
                    else:
                        msg += f"  ✅ *Цель достигнута! Допуск к сессии получен!*\n"
                else:
                    msg += f"  📊 *Нет числовых оценок для подсчёта*\n"
                    
                msg += "\n"
        else:
            msg += "*Оценки:* пока нет\n\n"
        
        # Раздел с пропусками
        msg += "*Пропуски:*\n"
        msg += f"⏰ Пропущено: *{total_hours}ч* из 20 допустимых\n"
        msg += f"🕐 Осталось: *{remaining_hours}ч*\n\n"
        
        # Статус
        if total_hours >= 20:
            msg += "⚠️ *Внимание:* лимит пропусков превышен!"
        elif total_hours >= 15:
            msg += "❗ *Предупреждение:* вы близки к лимиту пропусков."
        else:
            msg += "✅ *Статус:* всё в порядке."
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="student_main_menu"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=msg,
            parse_mode="Markdown",
            reply_markup=markup
        )
        
        logger.info(f"Табель успешно отправлен студенту {login}")
        
    except Exception as e:
        logger.error(f"Ошибка при получении табеля для {login}: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка при загрузке данных.")



@bot.callback_query_handler(func=lambda call: call.data == "student_view_schedule")
def handle_student_schedule(call):
    user_id = call.from_user.id
    current_login = get_current_student_login(user_id)

    if not current_login:
        bot.answer_callback_query(call.id, "❌ Ошибка авторизации. Войдите заново.")
        return

    logger.info(f"Студент {current_login} открыл раздел расписания")
    
    # Создаем меню выбора периода
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_today = types.InlineKeyboardButton("📅 На сегодня", callback_data="student_schedule_today")
    btn_tomorrow = types.InlineKeyboardButton("📅 На завтра", callback_data="student_schedule_tomorrow")
    btn_week = types.InlineKeyboardButton("📅 На неделю", callback_data="student_schedule_week")
    btn_next_week = types.InlineKeyboardButton("📅 След. неделя", callback_data="student_schedule_next_week")
    btn_main_menu = types.InlineKeyboardButton("🏠 Главное меню", callback_data="student_main_menu")
    markup.add(btn_today, btn_tomorrow, btn_week, btn_next_week, btn_main_menu)
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="📅 *Расписание*\n\nВыберите период для просмотра:",
        parse_mode="Markdown",
        reply_markup=markup
    )


# Обновляем обработчик для кнопок расписания абитуриентов
@bot.callback_query_handler(func=lambda call: call.data.startswith("student_schedule_"))
def handle_student_schedule_period(call):
    user_id = call.from_user.id
    current_login = get_current_student_login(user_id)

    if not current_login:
        bot.answer_callback_query(call.id, "❌ Ошибка авторизации. Войдите заново.")
        return

    period = call.data.replace("student_schedule_", "")
    logger.info(f"Студент {current_login} запросил расписание на {period}")
    
    try:
        from schedule_utils import get_week_type
        from datetime import datetime, timedelta
        
        # Отладочная информация
        logger.info(f"DEBUG: Обработка периода '{period}'")
        
        if period == "today":
            target_date = datetime.today().date()
            week_type = get_week_type(target_date)
            # Получаем английское название дня
            day_name_english = target_date.strftime("%A").lower()
            logger.info(f"DEBUG: Сегодня - дата: {target_date}, день: {day_name_english}, неделя: {week_type}")
            
            schedule = students.get_day_schedule(day_name_english, week_type)
            period_text = "сегодня"
            
        elif period == "tomorrow":
            target_date = datetime.today().date() + timedelta(days=1)
            week_type = get_week_type(target_date)
            day_name_english = target_date.strftime("%A").lower()
            logger.info(f"DEBUG: Завтра - дата: {target_date}, день: {day_name_english}, неделя: {week_type}")
            
            schedule = students.get_day_schedule(day_name_english, week_type)
            period_text = "завтра"
            
        elif period == "week":
            week_type = get_week_type(datetime.today().date())
            logger.info(f"DEBUG: Неделя - тип: {week_type}")
            
            schedule = students.get_week_schedule(week_type)
            period_text = "эту неделю"
            
        elif period == "next_week":
            # Получаем дату через неделю
            next_week_date = datetime.today().date() + timedelta(days=7)
            week_type = get_week_type(next_week_date)
            logger.info(f"DEBUG: След. неделя - дата: {next_week_date}, тип: {week_type}")
            
            schedule = students.get_week_schedule(week_type)
            period_text = "следующую неделю"
        else:
            logger.error(f"Неизвестный период: {period}")
            return
        
        logger.info(f"DEBUG: Получено расписаний: {len(schedule) if schedule else 0}")
        
        # Формируем сообщение с расписанием
        if not schedule:
            msg = f"⚠️ Расписание на {period_text} пока не составлено."
            logger.info(f"DEBUG: Расписание на {period_text} не найдено")
        else:
            if period in ["week", "next_week"]:
                # Форматирование для недели
                week_text = "*Чётная*" if week_type == "even" else "*Нечётная*"
                if period == "next_week":
                    msg = f"📅 *Расписание на {period_text} ({week_text})*\n\n"
                else:
                    msg = f"📅 *Расписание на {period_text} ({week_text})*\n\n"
                
                current_day = None
                for day, pair, time, subject, teacher, place in schedule:
                    if day != current_day:
                        if current_day is not None:
                            msg += "──────────────────────────\n\n"
                        msg += f" *{day}*\n"
                        current_day = day

                    msg += (
                        f" *{time}* — {subject or '—'}\n"
                        f" {teacher or '—'}\n"
                        f" {place or '—'}\n\n"
                    )
            else:
                # Форматирование для одного дня
                week_text = "чётная" if week_type == "even" else "нечётная"
                day_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
                day_name = day_names[target_date.weekday()]
                
                msg = f"📅 *Расписание на {period_text}*\n"
                msg += f"*{target_date.strftime('%d.%m.%Y')}, {day_name}, неделя {week_text}*\n\n"
                
                if schedule:
                    for day, pair, time, subject, teacher, place in schedule:
                        msg += (
                            f" *{time}* — {subject or '—'}\n"
                            f" {teacher or '—'}\n"
                            f" {place or '—'}\n\n"
                        )
                else:
                    msg += "🎉 Пар нет! Отдыхайте!"
        
        # Создаем кнопку "Назад"
        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="student_view_schedule")
        markup.add(btn_back)
        
        # Отправляем сообщение
        if call.message.content_type == 'text':
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=msg,
                parse_mode="Markdown",
                reply_markup=markup
            )
        else:
            # Если сообщение нельзя редактировать (например, содержит медиа), отправляем новое
            bot.send_message(
                call.message.chat.id,
                msg,
                parse_mode="Markdown",
                reply_markup=markup
            )
        
        logger.info(f"Расписание на {period} успешно отправлено студенту {current_login}")
        
    except Exception as e:
        logger.error(f"Ошибка при получении расписания для {current_login}: {e}")
        import traceback
        logger.error(f"Детали ошибки: {traceback.format_exc()}")
        bot.answer_callback_query(call.id, "❌ Ошибка при загрузке расписания.")


@bot.callback_query_handler(func=lambda call: call.data == "student_view_priority")
def handle_student_priority(call):
    user_id = call.from_user.id
    current_login = get_current_student_login(user_id)

    if not current_login:
        bot.answer_callback_query(call.id, "❌ Ошибка авторизации. Войдите заново.")
        return

    logger.info(f"Студент {current_login} запросил приоритеты")
    
    try:
        # Получаем данные студента для анализа приоритетов
        msg = "🎯 *Ваши учебные приоритеты*\n\n"
        
        # Анализ оценок
        grades = grades_db.get_student_grades(current_login)
        if grades:
            low_grades = []
            for subject, grade, grade_type, date, marked_by in grades:
                try:
                    if float(grade) < 3.0:
                        low_grades.append((subject, grade))
                except ValueError:
                    # Пропускаем нечисловые оценки
                    continue
            
            if low_grades:
                msg += "📉 *Предметы для улучшения:*\n"
                for subject, grade in low_grades:
                    msg += f"  • {subject}: {grade}\n"
                msg += "\n"
            else:
                msg += "✅ *Все оценки удовлетворительные*\n\n"
        else:
            msg += "📝 *Оценок пока нет*\n\n"
        
        # Анализ пропусков
        total_hours = attendance_db.get_student_total_hours(current_login)
        if total_hours >= 15:
            msg += f"⚠️ *Внимание:* у вас {total_hours}ч пропусков. Близко к лимиту!\n\n"
        elif total_hours >= 10:
            msg += f"ℹ️ *Информация:* у вас {total_hours}ч пропусков\n\n"
        else:
            msg += f"✅ *Пропуски:* {total_hours}ч - хороший показатель\n\n"
        
        # Рекомендации
        msg += "💡 *Рекомендации:*\n"
        if low_grades:
            msg += "• Сосредоточьтесь на предметах с низкими оценками\n"
        if total_hours >= 10:
            msg += "• Старайтесь не пропускать занятия\n"
        if not low_grades and total_hours < 10:
            msg += "• Продолжайте в том же духе! 👍\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="student_main_menu"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=msg,
            parse_mode="Markdown",
            reply_markup=markup
        )
        
        logger.info(f"Приоритеты успешно отправлены студенту {current_login}")
        
    except Exception as e:
        logger.error(f"Ошибка при анализе приоритетов для {current_login}: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка при анализе данных.")


# И только потом идет общий обработчик
@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    try:
        # Обрабатываем все callback данные как обычно
        if call.data == "student_main_menu":
            handle_student_main_menu(call)
        elif call.data == "student_view_grades":
            handle_student_grades(call)
        elif call.data == "student_view_schedule":
            handle_student_schedule(call)
        elif call.data == "student_view_priority":
            handle_student_priority(call)  # Теперь эта функция определена
        elif call.data.startswith("student_schedule_"):
            handle_student_schedule_period(call)
        # Добавьте другие обработчики по необходимости
            
    except Exception as e:
        if "query is too old" in str(e) or "query ID is invalid" in str(e):
            # Игнорируем ошибку "слишком старый запрос"
            logger.warning(f"Истек срок действия callback запроса: {call.data}")
            try:
                bot.answer_callback_query(call.id, "⚠️ Время действия кнопки истекло. Пожалуйста, выберите действие снова.")
            except:
                pass
        else:
            # Логируем другие ошибки
            logger.error(f"Ошибка в callback обработчике: {e}")


if __name__ == "__main__":
    try:
        logger.info("Запуск цикла обработки сообщений для бота абитуриентов...")
        bot.polling(none_stop=True)
    except KeyboardInterrupt:
        logger.info("Остановка бота абитуриентов пользователем (Ctrl+C).")
    except Exception as e:
        logger.exception(f"Ошибка в работе бота абитуриентов: {e}")
    finally:
        logger.info("Бот абитуриентов завершил работу.")