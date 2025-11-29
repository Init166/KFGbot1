import database
import logging
from schedule_utils import get_week_type


logger = logging.getLogger(__name__)


def get_week_schedule(week_type):
    """
    Получить расписание на неделю
    """
    conn = database.create_connection()
    cursor = conn.cursor()
    
    try:
        # Порядок дней недели для правильной сортировки
        day_order = {
            'monday': 1, 'понедельник': 1,
            'tuesday': 2, 'вторник': 2, 
            'wednesday': 3, 'среда': 3,
            'thursday': 4, 'четверг': 4,
            'friday': 5, 'пятница': 5,
            'saturday': 6, 'суббота': 6,
            'sunday': 7, 'воскресенье': 7
        }
        
        cursor.execute("""
            SELECT day, pair_number, time, subject, teacher, classroom 
            FROM schedule 
            WHERE week_type = ? OR week_type = 'both'
            ORDER BY 
                CASE day 
                    WHEN 'monday' THEN 1
                    WHEN 'понедельник' THEN 1
                    WHEN 'tuesday' THEN 2  
                    WHEN 'вторник' THEN 2
                    WHEN 'wednesday' THEN 3
                    WHEN 'среда' THEN 3
                    WHEN 'thursday' THEN 4
                    WHEN 'четверг' THEN 4
                    WHEN 'friday' THEN 5
                    WHEN 'пятница' THEN 5
                    WHEN 'saturday' THEN 6
                    WHEN 'суббота' THEN 6
                    WHEN 'sunday' THEN 7
                    WHEN 'воскресенье' THEN 7
                    ELSE 8
                END,
                pair_number
        """, (week_type,))
        
        schedule = cursor.fetchall()
        return schedule
    except Exception as e:
        print(f"Ошибка при получении расписания на неделю: {e}")
        return []
    finally:
        conn.close()

def get_day_schedule(day_name_english, week_type):
    """
    Получить расписание на конкретный день
    """
    conn = database.create_connection()
    if conn is None:
        return None
    
    try:
        cursor = conn.cursor()
        
        # Преобразуем английское название дня в русское
        days_mapping = {
            'monday': 'Понедельник',
            'tuesday': 'Вторник',
            'wednesday': 'Среда', 
            'thursday': 'Четверг',
            'friday': 'Пятница',
            'saturday': 'Суббота',
            'sunday': 'Воскресенье'
        }
        
        day_russian = days_mapping.get(day_name_english.lower(), day_name_english)
        
        cursor.execute('''
            SELECT day, pair_number, time, subject, teacher, classroom 
            FROM schedule 
            WHERE day = ? AND week_type = ? 
            ORDER BY pair_number
        ''', (day_russian, week_type))
        
        schedule = cursor.fetchall()
        return schedule
        
    except Exception as e:
        print(f"Ошибка при получении расписания на день: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_week_schedule(week_type):
    """
    Получить расписание на всю неделю
    """
    conn = database.create_connection()
    if conn is None:
        return None
    
    try:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT day, pair_number, time, subject, teacher, classroom 
            FROM schedule 
            WHERE week_type = ? 
            ORDER BY 
                CASE day
                    WHEN 'Понедельник' THEN 1
                    WHEN 'Вторник' THEN 2
                    WHEN 'Среда' THEN 3
                    WHEN 'Четверг' THEN 4
                    WHEN 'Пятница' THEN 5
                    WHEN 'Суббота' THEN 6
                    WHEN 'Воскресенье' THEN 7
                END,
                pair_number
        ''', (week_type,))
        
        schedule = cursor.fetchall()
        return schedule
        
    except Exception as e:
        print(f"Ошибка при получении расписания на неделю: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_day_schedule(day_name_english, week_type):
    """
    Получить расписание на конкретный день
    """
    conn = database.create_connection()
    if conn is None:
        return None
    
    try:
        cursor = conn.cursor()
        
        # Преобразуем английское название дня в русское
        days_mapping = {
            'monday': 'Понедельник',
            'tuesday': 'Вторник',
            'wednesday': 'Среда', 
            'thursday': 'Четверг',
            'friday': 'Пятница',
            'saturday': 'Суббота',
            'sunday': 'Воскресенье'
        }
        
        day_russian = days_mapping.get(day_name_english.lower(), day_name_english)
        
        print(f"DEBUG: Поиск расписания для дня '{day_russian}' (англ: '{day_name_english}'), неделя: '{week_type}'")
        
        cursor.execute('''
            SELECT day, pair_number, time, subject, teacher, classroom 
            FROM schedule 
            WHERE day = ? AND week_type = ? 
            ORDER BY pair_number
        ''', (day_russian, week_type))
        
        schedule = cursor.fetchall()
        print(f"DEBUG: Найдено {len(schedule)} пар для {day_russian}")
        return schedule
        
    except Exception as e:
        print(f"Ошибка при получении расписания на день: {e}")
        return None
    finally:
        if conn:
            conn.close()


def check_schedule_days():
    """
    Проверить, какие дни есть в расписании
    """
    conn = database.create_connection()
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

# Вызовите эту функцию после заполнения базы
check_schedule_days()


def get_current_student_login(user_id):
    """
    Получить текущий логин студента из сессии
    """
    if user_id in student_sessions:
        return student_sessions[user_id]["current_login"]
    return None


def get_week_schedule(week_type):
    """
    Получить расписание на всю неделю для студентов
    """
    conn = database.create_connection()
    if conn is None:
        return None
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT day, pair_number, time, subject, teacher, classroom 
            FROM schedule 
            WHERE week_type = ? 
            ORDER BY 
                CASE day
                    WHEN 'Понедельник' THEN 1
                    WHEN 'Вторник' THEN 2
                    WHEN 'Среда' THEN 3
                    WHEN 'Четверг' THEN 4
                    WHEN 'Пятница' THEN 5
                    WHEN 'Суббота' THEN 6
                    WHEN 'Воскресенье' THEN 7
                END,
                pair_number
        """, (week_type,))
        
        schedule = cursor.fetchall()
        return schedule
        
    except Exception as e:
        print(f"Ошибка при получении расписания на неделю: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_student_info(login):
    """
    Получить информацию о студенте по логину
    """
    conn = database.create_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT name, group_name FROM students WHERE name = ?", (login,))
        student = cursor.fetchone()
        
        if student:
            print(f"DEBUG get_student_info: Найден студент {student[0]}")
            return student
        else:
            print(f"DEBUG get_student_info: Студент не найден: {login}")
            return None
    except Exception as e:
        print(f"Ошибка при получении информации о студенте: {e}")
        return None
    finally:
        conn.close()


def send_group_message(group_name, message_text, bot):
    """Отправка сообщения всем студентам группы"""
    conn = database.create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM students WHERE group_name = ? AND telegram_id IS NOT NULL", (group_name,))
    rows = cursor.fetchall()
    conn.close()
    for row in rows:
        try:
            bot.send_message(row[0], f"📚 Сообщение для группы {group_name}:\n{message_text}")
        except Exception as e:
            logger.warning(f"Не удалось отправить сообщение студенту {row[0]}: {e}")

