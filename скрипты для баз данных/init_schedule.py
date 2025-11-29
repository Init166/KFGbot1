import database

def init_schedule_data():
    conn = database.create_connection()
    cursor = conn.cursor()
    
    # Создаем таблицу если её нет
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            pair_number INTEGER NOT NULL,
            time TEXT NOT NULL,
            subject TEXT,
            teacher TEXT,
            classroom TEXT,
            week_type TEXT NOT NULL DEFAULT 'both'
        )
    ''')
    
    # Добавляем тестовые данные
    test_schedule = [
        # Понедельник
        ('monday', 1, '9:00-10:30', 'Математика', 'Иванов И.И.', 'А-101', 'both'),
        ('monday', 2, '10:45-12:15', 'Физика', 'Петров П.П.', 'А-102', 'both'),
        ('monday', 3, '13:00-14:30', 'Программирование', 'Сидоров С.С.', 'Б-201', 'both'),
        
        # Вторник
        ('tuesday', 1, '9:00-10:30', 'Английский язык', 'Smith J.', 'Л-101', 'both'),
        ('tuesday', 2, '10:45-12:15', 'Базы данных', 'Кузнецов К.К.', 'Б-202', 'both'),
        
        # Среда
        ('wednesday', 1, '9:00-10:30', 'Веб-разработка', 'Васильев В.В.', 'Б-203', 'both'),
        ('wednesday', 2, '10:45-12:15', 'Сети', 'Николаев Н.Н.', 'А-103', 'both'),
        
        # Четверг
        ('thursday', 1, '9:00-10:30', 'ООП', 'Федоров Ф.Ф.', 'Б-204', 'both'),
        ('thursday', 2, '10:45-12:15', 'Алгоритмы', 'Дмитриев Д.Д.', 'А-104', 'both'),
        
        # Пятница
        ('friday', 1, '9:00-10:30', 'Проектная деятельность', 'Алексеев А.А.', 'Б-205', 'both'),
        ('friday', 2, '10:45-12:15', 'Физкультура', 'Спортов С.С.', 'Спортзал', 'both'),
    ]
    
    cursor.executemany('''
        INSERT OR REPLACE INTO schedule (day, pair_number, time, subject, teacher, classroom, week_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', test_schedule)
    
    conn.commit()
    conn.close()
    print("✅ Таблица расписания создана и заполнена тестовыми данными!")

if __name__ == "__main__":
    init_schedule_data()