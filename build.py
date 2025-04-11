import os
import sys
import shutil
import PyInstaller.__main__

def build_executable():
    """Сборка исполняемого файла для Windows"""
    
    # Очистка старых сборок
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    
    # Определяем пути к ресурсам
    script_path = "create.card.py"
    icon_path = os.path.join("data", "icon.ico") if os.path.exists(os.path.join("data", "icon.ico")) else None
    
    # Формируем команду для PyInstaller
    command = [
        script_path,
        '--onefile',  # Собрать в один файл
        '--console',  # Изменено с --noconsole на --console
        '--name=VCard_Generator',  # Имя выходного файла
        '--add-data=data;data',  # Добавляем папку с ресурсами
        '--hidden-import=PIL',
        '--hidden-import=reportlab',
        '--hidden-import=barcode',
        '--hidden-import=argparse',  # Добавляем новую зависимость
    ]
    
    # Добавляем иконку, если она существует
    if icon_path:
        command.append(f'--icon={icon_path}')
    
    try:
        # Запускаем сборку
        PyInstaller.__main__.run(command)
        
        print("\nСборка успешно завершена!")
        print(f"Исполняемый файл находится в папке: {os.path.abspath('dist')}")
        
    except Exception as e:
        print(f"Ошибка при сборке: {e}")

if __name__ == "__main__":
    build_executable() 