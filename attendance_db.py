# attendance_db.py
import sqlite3
import database
from database import create_connection  



def init_attendance_db():
    conn = database.create_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_login TEXT NOT NULL,
            date TEXT NOT NULL,
            subject TEXT NOT NULL,
            hours INTEGER NOT NULL,
            reason TEXT,
            marked_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

def remove_absence(student_login, hours_to_remove):
    """Удаляет последние часы пропусков у студента"""
    conn = database.create_connection()  # Используем database.create_connection
    cursor = conn.cursor()
    
    try:
        # Получаем текущие пропуски студента в порядке от новых к старым
        cursor.execute("""
            SELECT id, hours FROM attendance 
            WHERE student_login = ? 
            ORDER BY date DESC, id DESC
        """, (student_login,))
        
        absences = cursor.fetchall()
        total_removed = 0
        remaining_hours_to_remove = hours_to_remove
        
        if not absences:
            return 0
            
        # Удаляем часы из записей, начиная с самых новых
        for absence_id, hours in absences:
            if remaining_hours_to_remove <= 0:
                break
                
            if hours <= remaining_hours_to_remove:
                # Если в этой записи часов меньше или равно тому, что нужно удалить - удаляем всю запись
                cursor.execute("DELETE FROM attendance WHERE id = ?", (absence_id,))
                total_removed += hours
                remaining_hours_to_remove -= hours
            else:
                # Если в записи часов больше - уменьшаем количество часов
                new_hours = hours - remaining_hours_to_remove
                cursor.execute("UPDATE attendance SET hours = ? WHERE id = ?", (new_hours, absence_id))
                total_removed += remaining_hours_to_remove
                remaining_hours_to_remove = 0
        
        conn.commit()
        return total_removed
        
    except Exception as e:
        conn.rollback()
        print(f"Ошибка при удалении пропусков для {student_login}: {e}")
        return 0
    finally:
        conn.close()

def reset_all_absences():
    """Сбрасывает все пропуски у всех студентов"""
    conn = database.create_connection()  # Используем database.create_connection
    cursor = conn.cursor()
    
    try:
        # Просто удаляем все записи из таблицы attendance
        cursor.execute("DELETE FROM attendance")
        conn.commit()
        print("✅ Все пропуски сброшены")
        return True
    except Exception as e:
        conn.rollback()
        print(f"Ошибка при сбросе пропусков: {e}")
        return False
    finally:
        conn.close()

def get_student_total_hours(student_login):
    """Получает общее количество часов пропусков студента"""
    conn = database.create_connection()  # Используем database.create_connection
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT COALESCE(SUM(hours), 0) 
            FROM attendance 
            WHERE student_login = ?
        """, (student_login,))
        
        result = cursor.fetchone()
        return result[0] if result else 0
    except Exception as e:
        print(f"Ошибка при получении часов пропусков для {student_login}: {e}")
        return 0
    finally:
        conn.close()

def add_absence(student_login, subject, hours, reason, marked_by, date):
    """Добавление пропуска"""
    conn = database.create_connection()  # Используем database.create_connection
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO attendance (student_login, subject, hours, reason, marked_by, date)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (student_login, subject, hours, reason, marked_by, date))

    conn.commit()
    conn.close()

def get_student_absence_details(student_login):
    """Получает детальную информацию о пропусках студента"""
    conn = create_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT date, hours, reason, marked_by 
        FROM attendance 
        WHERE student_login = ? 
        ORDER BY date DESC, id DESC
    """, (student_login,))
    
    absences = cursor.fetchall()
    conn.close()
    return absences




def remove_absence_hours(student_login, hours_to_remove):
    """Удаление часов пропусков у студента"""
    conn = database.create_connection()
    cursor = conn.cursor()

    # Получаем все пропуски студента, отсортированные по дате (сначала старые)
    cursor.execute("""
        SELECT id, hours FROM attendance 
        WHERE student_login = ? 
        ORDER BY date ASC, id ASC
    """, (student_login,))

    absences = cursor.fetchall()
    remaining_hours_to_remove = hours_to_remove
    removed_count = 0

    # Удаляем часы из старых пропусков
    for absence_id, hours in absences:
        if remaining_hours_to_remove <= 0:
            break

        if hours <= remaining_hours_to_remove:
            # Удаляем всю запись
            cursor.execute("DELETE FROM attendance WHERE id = ?", (absence_id,))
            remaining_hours_to_remove -= hours
            removed_count += hours
        else:
            # Уменьшаем количество часов в записи
            cursor.execute("UPDATE attendance SET hours = ? WHERE id = ?", 
                         (hours - remaining_hours_to_remove, absence_id))
            removed_count += remaining_hours_to_remove
            remaining_hours_to_remove = 0

    conn.commit()
    conn.close()
    return removed_count

def get_student_total_hours(student_login):
    conn = database.create_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT SUM(hours) FROM attendance WHERE student_login = ?
    """, (student_login,))
    result = cursor.fetchone()
    conn.close()

    return result[0] or 0