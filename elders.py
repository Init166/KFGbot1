import database
import logging
import database
import sqlite3
from schedule_utils import get_week_type


logger = logging.getLogger(__name__)


def get_week_schedule(week_type):
    conn = sqlite3.connect("schedule.db")
    cursor = conn.cursor()
    cursor.execute("""
    SELECT day, pair_number, start_time, subject, teacher, place
    FROM weekly_schedule
    WHERE week_type = ?
        ORDER BY 
            CASE
                WHEN day = 'Понедельник' THEN 1
                WHEN day = 'Вторник' THEN 2
                WHEN day = 'Среда' THEN 3
                WHEN day = 'Четверг' THEN 4
                WHEN day = 'Пятница' THEN 5
                WHEN day = 'Суббота' THEN 6
                ELSE 7
            END, pair_number
""", (week_type,))

    rows = cursor.fetchall()
    conn.close()
    return rows


def set_lesson(week_type, day, pair_number, start_time, subject, teacher):
    """Добавляет или изменяет пару"""
    conn = database.create_connection()
    cursor = conn.cursor()
    # Проверяем, есть ли уже такая пара
    cursor.execute(
        "SELECT id FROM weekly_schedule WHERE week_type = ? AND day = ? AND pair_number = ?",
        (week_type, day, pair_number)
    )
    row = cursor.fetchone()
    if row:
        # Обновляем
        cursor.execute(
            "UPDATE weekly_schedule SET start_time = ?, subject = ?, teacher = ? WHERE id = ?",
            (start_time, subject, teacher, row[0])
        )
    else:
        # Вставляем новую
        cursor.execute(
            "INSERT INTO weekly_schedule (week_type, day, pair_number, start_time, subject, teacher) VALUES (?, ?, ?, ?, ?, ?)",
            (week_type, day, pair_number, start_time, subject, teacher)
        )
    conn.commit()
    conn.close()

def get_elder_info(telegram_id):
    """Получение информации о старосте по Telegram ID"""
    conn = database.create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT login, telegram_id FROM elders WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def send_group_update(group_name, message_text, bot):
    """Отправка уведомления всем старостам определённой группы"""
    conn = database.create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM elders WHERE telegram_id IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()
    for row in rows:
        try:
            bot.send_message(row[0], f"📢 Обновление для группы {group_name}:\n{message_text}")
        except Exception as e:
            logger.warning(f"Не удалось отправить сообщение старосте {row[0]}: {e}")
