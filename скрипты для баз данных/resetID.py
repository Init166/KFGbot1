import database

def reset_telegram_ids():
    conn = database.create_connection()
    cursor = conn.cursor()
    
    # Сбрасываем все telegram_id
    cursor.execute("UPDATE students SET telegram_id = NULL")
    cursor.execute("UPDATE elders SET telegram_id = NULL")
    
    conn.commit()
    conn.close()
    print("✅ Все telegram_id сброшены!")

if __name__ == "__main__":
    reset_telegram_ids()