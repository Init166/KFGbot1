# priority_db.py
import sqlite3
import database

def init_priority_db():
    """Инициализация таблицы для приоритетных команд"""
    conn = database.create_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS priority_teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            student_login TEXT NOT NULL,
            team_type TEXT NOT NULL, -- 'priority', 'fire', 'reserve'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

def calculate_priority_teams(subject):
    """Автоматическое распределение студентов по командам на основе статистики"""
    conn = database.create_connection()
    cursor = conn.cursor()
    
    # Получаем всех студентов и их статистику по предмету
    cursor.execute("""
        SELECT 
            s.name,
            COUNT(g.grade) as grade_count,
            COALESCE(SUM(a.hours), 0) as absence_hours,
            AVG(CASE 
                WHEN CAST(g.grade AS REAL) IS NOT NULL THEN CAST(g.grade AS REAL)
                ELSE NULL 
            END) as avg_grade
        FROM students s
        LEFT JOIN grades g ON s.name = g.student_login AND g.subject = ?
        LEFT JOIN attendance a ON s.name = a.student_login
        GROUP BY s.name
        ORDER BY grade_count ASC, absence_hours DESC, avg_grade ASC
    """, (subject,))
    
    students_data = cursor.fetchall()
    conn.close()
    
    priority_team = []
    fire_team = []
    reserve_team = []
    
    for student_name, grade_count, absence_hours, avg_grade in students_data:
        avg_grade = avg_grade or 0
        
        # Критерии распределения
        if (grade_count <= 2 and absence_hours >= 5) or (avg_grade < 2.5 and grade_count > 0):
            # Приоритет: мало оценок + много пропусков ИЛИ очень низкий средний балл
            priority_team.append({
                'name': student_name,
                'grade_count': grade_count,
                'absence_hours': absence_hours,
                'avg_grade': round(avg_grade, 2) if avg_grade else 0
            })
        elif (grade_count <= 4 and absence_hours >= 3) or (avg_grade < 3.5 and grade_count > 0):
            # Пожарная команда: среднее количество оценок + пропуски ИЛИ низкий средний балл
            fire_team.append({
                'name': student_name,
                'grade_count': grade_count,
                'absence_hours': absence_hours,
                'avg_grade': round(avg_grade, 2) if avg_grade else 0
            })
        else:
            # Запас: много оценок, мало пропусков, высокий средний балл
            reserve_team.append({
                'name': student_name,
                'grade_count': grade_count,
                'absence_hours': absence_hours,
                'avg_grade': round(avg_grade, 2) if avg_grade else 0
            })
    
    return priority_team, fire_team, reserve_team

def save_priority_teams(subject, priority_team, fire_team, reserve_team):
    """Сохранение распределения по командам в базу"""
    conn = database.create_connection()
    cursor = conn.cursor()
    
    # Удаляем старые записи для этого предмета
    cursor.execute("DELETE FROM priority_teams WHERE subject = ?", (subject,))
    
    # Сохраняем новые записи
    for student in priority_team:
        cursor.execute("""
            INSERT INTO priority_teams (subject, student_login, team_type)
            VALUES (?, ?, ?)
        """, (subject, student['name'], 'priority'))
    
    for student in fire_team:
        cursor.execute("""
            INSERT INTO priority_teams (subject, student_login, team_type)
            VALUES (?, ?, ?)
        """, (subject, student['name'], 'fire'))
    
    for student in reserve_team:
        cursor.execute("""
            INSERT INTO priority_teams (subject, student_login, team_type)
            VALUES (?, ?, ?)
        """, (subject, student['name'], 'reserve'))
    
    conn.commit()
    conn.close()

def get_subjects_with_grades():
    """Получение списка предметов, по которым есть оценки"""
    conn = database.create_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT subject FROM grades ORDER BY subject")
    subjects = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return subjects