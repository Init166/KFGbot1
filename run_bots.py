import subprocess
import sys
import time
import os
import signal
import threading
from datetime import datetime

class BotManager:
    def __init__(self):
        self.processes = {}
        self.running = False
        self.restart_attempts = {}  # Счетчик попыток перезапуска
        self.max_restart_attempts = 5  # Максимальное количество попыток перезапуска
        self.restart_delay = 10  # Задержка перед перезапуском (секунды)
        
    def log(self, message):
        """Логирование с временной меткой"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    def start_bot(self, bot_name, bot_file):
        """Запуск одного бота"""
        try:
            self.log(f"🚀 Запуск {bot_name}...")
            process = subprocess.Popen(
                [sys.executable, bot_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.processes[bot_name] = process
            self.restart_attempts[bot_name] = 0
            
            # Запускаем мониторинг вывода в отдельном потоке
            threading.Thread(
                target=self.monitor_bot_output,
                args=(bot_name, process),
                daemon=True
            ).start()
            
            self.log(f"✅ {bot_name} запущен (PID: {process.pid})")
            return True
            
        except Exception as e:
            self.log(f"❌ Ошибка запуска {bot_name}: {e}")
            return False
    
    def monitor_bot_output(self, bot_name, process):
        """Мониторинг вывода бота"""
        while process.poll() is None:  # Пока процесс работает
            try:
                output = process.stdout.readline()
                if output:
                    self.log(f"{bot_name}: {output.strip()}")
            except:
                pass
    
    def stop_bot(self, bot_name):
        """Остановка одного бота"""
        if bot_name in self.processes:
            self.log(f"🛑 Остановка {bot_name}...")
            process = self.processes[bot_name]
            try:
                # Отправляем сигнал завершения
                process.terminate()
                # Ждем завершения
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Принудительное завершение
                process.kill()
                process.wait()
            except Exception as e:
                self.log(f"❌ Ошибка остановки {bot_name}: {e}")
            
            del self.processes[bot_name]
            self.log(f"✅ {bot_name} остановлен")
    
    def stop_all_bots(self):
        """Остановка всех ботов"""
        self.log("🛑 Остановка всех ботов...")
        self.running = False
        
        for bot_name in list(self.processes.keys()):
            self.stop_bot(bot_name)
        
        self.log("✅ Все боты остановлены")
    
    def check_bots_health(self):
        """Проверка состояния ботов и перезапуск при необходимости"""
        for bot_name, process in list(self.processes.items()):
            return_code = process.poll()
            
            if return_code is not None:  # Бот завершился
                self.log(f"⚠️ {bot_name} завершил работу с кодом: {return_code}")
                
                # Проверяем количество попыток перезапуска
                if self.restart_attempts[bot_name] < self.max_restart_attempts:
                    self.restart_attempts[bot_name] += 1
                    self.log(f"🔄 Перезапуск {bot_name} (попытка {self.restart_attempts[bot_name]}/{self.max_restart_attempts})...")
                    
                    # Задержка перед перезапуском
                    time.sleep(self.restart_delay)
                    
                    # Перезапускаем бота
                    bot_file = "main.py" if bot_name == "Бот старост" else "main2.py"
                    self.start_bot(bot_name, bot_file)
                else:
                    self.log(f"❌ Превышено максимальное количество попыток перезапуска для {bot_name}")
                    self.stop_all_bots()
    
    def start_monitoring(self):
        """Запуск мониторинга ботов"""
        self.running = True
        self.log("🔍 Запуск мониторинга ботов...")
        
        while self.running:
            try:
                self.check_bots_health()
                time.sleep(5)  # Проверяем каждые 5 секунд
            except KeyboardInterrupt:
                self.stop_all_bots()
                break
            except Exception as e:
                self.log(f"❌ Ошибка в мониторинге: {e}")
                time.sleep(10)
    
    def show_menu(self):
        """Показать меню выбора"""
        print("\n" + "="*50)
        print("🤖 МЕНЕДЖЕР ЗАПУСКА БОТОВ")
        print("="*50)
        print("1 - Запустить бота для абитуриентов (main2.py)")
        print("2- Запустить бота для старост (main.py)")
        print("3 - Запустить обоих ботов")
        print("4 - Остановить всех ботов и выйти")
        print("="*50)
    
    def run_interactive(self):
        """Интерактивный режим запуска"""
        try:
            while True:
                self.show_menu()
                choice = input("\n🎯 Выберите действие (1-4): ").strip()
                
                if choice == "1":
                    self.stop_all_bots()
                    if self.start_bot("Бот абитуриентов", "main2.py"):
                        self.start_monitoring()
                
                elif choice == "2":
                    self.stop_all_bots()
                    if self.start_bot("Бот старост", "main.py"):
                        self.start_monitoring()
                
                elif choice == "3":
                    self.stop_all_bots()
                    success1 = self.start_bot("Бот старост", "main.py")
                    success2 = self.start_bot("Бот абитуриентов", "main2.py")
                    if success1 or success2:
                        self.start_monitoring()
                
                elif choice == "4":
                    self.stop_all_bots()
                    self.log("👋 Выход из программы")
                    break
                
                else:
                    print("❌ Неверный выбор. Попробуйте снова.")
                    
        except KeyboardInterrupt:
            self.stop_all_bots()
            self.log("👋 Выход из программы (Ctrl+C)")

def main():
    """Основная функция"""
    print("🤖 Инициализация менеджера ботов...")
    
    # Создаем менеджер
    manager = BotManager()
    
    # Обработчик сигналов для graceful shutdown
    def signal_handler(signum, frame):
        print(f"\n🛑 Получен сигнал {signum}, остановка ботов...")
        manager.stop_all_bots()
        sys.exit(0)
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Запускаем интерактивный режим
        manager.run_interactive()
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        manager.stop_all_bots()

if __name__ == "__main__":
    main()