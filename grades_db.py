# grades_db.py
import sqlite3
import database
from database import create_connection


# Если есть что-то подобное, используйте это:
def get_connection():
    return sqlite3.connect("database.db")

# Тогда в get_student_average используйте:
conn = get_connection()

def init_grades_db():
    """Инициализация таблицы оценок"""
    conn = database.create_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_login TEXT NOT NULL,
            date TEXT NOT NULL,
            subject TEXT NOT NULL,
            grade TEXT NOT NULL,
            grade_type TEXT NOT NULL, -- 'practice', 'seminar', 'exam', etc.
            marked_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

def add_grade(student_login, subject, grade, grade_type, marked_by, date):
    """Добавление оценки"""
    conn = database.create_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO grades (student_login, subject, grade, grade_type, marked_by, date)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (student_login, subject, grade, grade_type, marked_by, date))

    conn.commit()
    conn.close()


def get_student_grades_by_subject(student_login, subject):
    """Получить все оценки студента по конкретному предмету"""
    conn = create_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, grade, grade_type, date, marked_by 
        FROM grades 
        WHERE student_login = ? AND subject = ?
        ORDER BY date DESC
    """, (student_login, subject))
    
    grades = cursor.fetchall()
    conn.close()
    
    return grades

def get_all_subjects():
    """Получает список всех предметов, по которым есть оценки"""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT subject FROM grades ORDER BY subject")
    subjects = [row[0] for row in cursor.fetchall()]
    conn.close()
    return subjects


def get_student_subjects(student_login):
    """
    Получить список предметов, по которым у студента есть оценки
    """
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT DISTINCT subject 
            FROM grades 
            WHERE student_login = ?
            ORDER BY subject
        """, (student_login,))
        
        subjects = [row[0] for row in cursor.fetchall()]
        return subjects
    except Exception as e:
        print(f"Ошибка при получении предметов студента: {e}")
        return []
    finally:
        conn.close()

def delete_last_grade(student_name, subject):
    """
    Удаляет последнюю оценку студента по предмету
    """
    try:
        conn = create_connection()
        cursor = conn.cursor()
        
        # Находим ID последней оценки
        cursor.execute("""
            SELECT id FROM grades 
            WHERE student_login = ? AND subject = ? 
            ORDER BY date DESC, id DESC 
            LIMIT 1
        """, (student_name, subject))
        
        result = cursor.fetchone()
        
        if result:
            grade_id = result[0]
            # Удаляем оценку
            cursor.execute("DELETE FROM grades WHERE id = ?", (grade_id,))
            conn.commit()
            conn.close()
            return True
        else:
            conn.close()
            return False
            
    except Exception as e:
        print(f"Ошибка при удалении оценки: {e}")
        return False

def get_student_grades(student_login, subject=None):
    """Получение всех оценок студента"""
    conn = database.create_connection()
    cursor = conn.cursor()

    if subject:
        cursor.execute("""
            SELECT subject, grade, grade_type, date, marked_by 
            FROM grades 
            WHERE student_login = ? AND subject = ?
            ORDER BY date DESC
        """, (student_login, subject))
    else:
        cursor.execute("""
            SELECT subject, grade, grade_type, date, marked_by 
            FROM grades 
            WHERE student_login = ? 
            ORDER BY subject, date DESC
        """, (student_login,))

    grades = cursor.fetchall()
    conn.close()
    return grades

# Добавьте эти функции в grades_db.py

def get_student_subjects(student_login):
    """Получение списка предметов студента"""
    conn = database.create_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT subject FROM grades 
        WHERE student_login = ? 
        ORDER BY subject
    """, (student_login,))

    subjects = [row[0] for row in cursor.fetchall()]
    conn.close()
    return subjects

def get_student_grades_by_subject(student_login, subject):
    """Получение всех оценок студента по конкретному предмету"""
    conn = database.create_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, grade, grade_type, date, marked_by 
        FROM grades 
        WHERE student_login = ? AND subject = ?
        ORDER BY date DESC, id DESC
    """, (student_login, subject))

    grades = cursor.fetchall()
    conn.close()
    return grades

# Добавьте эту функцию в grades_db.py
def delete_grade(grade_id):
    """Удаляет оценку по ID"""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM grades WHERE id = ?", (grade_id,))
    conn.commit()
    conn.close()
    return True

def delete_last_grade(student_login, subject):
    """Удаление последней оценки студента по предмету"""
    conn = database.create_connection()
    cursor = conn.cursor()

    # Находим ID последней оценки
    cursor.execute("""
        SELECT id FROM grades 
        WHERE student_login = ? AND subject = ?
        ORDER BY date DESC, id DESC 
        LIMIT 1
    """, (student_login, subject))

    grade = cursor.fetchone()
    if grade:
        cursor.execute("DELETE FROM grades WHERE id = ?", (grade[0],))
    
    conn.commit()
    conn.close()
    return grade is not None

def delete_specific_grades(student_login, subject, grades_to_delete):
    """Удаление конкретных оценок"""
    conn = database.create_connection()
    cursor = conn.cursor()

    deleted_count = 0
    for grade_value in grades_to_delete:
        # Находим первую подходящую оценку
        cursor.execute("""
            SELECT id FROM grades 
            WHERE student_login = ? AND subject = ? AND grade = ?
            ORDER BY date DESC, id DESC 
            LIMIT 1
        """, (student_login, subject, grade_value))

        grade = cursor.fetchone()
        if grade:
            cursor.execute("DELETE FROM grades WHERE id = ?", (grade[0],))
            deleted_count += 1
    
    conn.commit()
    conn.close()
    return deleted_count

def delete_subject(student_login, subject):
    """Удалить все оценки студента по предмету"""
    conn = create_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM grades WHERE student_login = ? AND subject = ?", (student_login, subject))
    
    conn.commit()
    conn.close()

def get_student_average(student_login, subject):
    """
    Получить средний балл студента по предмету
    """
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT grade 
            FROM grades 
            WHERE student_login = ? AND subject = ?
        """, (student_login, subject))
        
        grades = [row[0] for row in cursor.fetchall()]
        
        if not grades:
            return None
        
        # Преобразуем оценки в числа (игнорируем нечисловые)
        numeric_grades = []
        for grade in grades:
            try:
                # Если оценка содержит несколько чисел (например, "4 5 3"), разбиваем их
                if ' ' in grade:
                    multiple_grades = grade.split()
                    for g in multiple_grades:
                        numeric_grade = float(g)
                        numeric_grades.append(numeric_grade)
                else:
                    numeric_grade = float(grade)
                    numeric_grades.append(numeric_grade)
            except ValueError:
                # Пропускаем нечисловые оценки (зачет/незачет и т.д.)
                continue
        
        if not numeric_grades:
            return None
            
        average = sum(numeric_grades) / len(numeric_grades)
        return round(average, 2)
        
    except Exception as e:
        print(f"Ошибка при расчете среднего балла: {e}")
        return None
    finally:
        conn.close()

def get_group_grades_summary(group_name):
    """Получить сводку по оценкам для всей группы"""
    conn = create_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            s.name as student_name,
            g.subject,
            ROUND(AVG(CASE 
                WHEN g.grade IN ('5', '4', '3', '2', '1') THEN CAST(g.grade AS REAL)
                WHEN g.grade = '5+' THEN 5.5
                WHEN g.grade = '4+' THEN 4.5
                WHEN g.grade = '3+' THEN 3.5
                WHEN g.grade = '2+' THEN 2.5
                ELSE NULL
            END), 2) as avg_grade,
            COUNT(g.grade) as grade_count
        FROM students s
        LEFT JOIN grades g ON s.name = g.student_login
        WHERE s.group_name = ?
        GROUP BY s.name, g.subject
        ORDER BY s.name, g.subject
    """, (group_name,))
    
    summary = cursor.fetchall()
    conn.close()
    
    return summary

def get_subjects_list():
    """Получение списка всех предметов"""
    conn = database.create_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT subject FROM grades ORDER BY subject")
    subjects = [row[0] for row in cursor.fetchall()]
    conn.close()
    return subjects