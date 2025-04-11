import csv
import os
import sys
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageFont, ImageDraw
import random
import logging
import traceback
from datetime import datetime
import argparse

# --- ПАРАМЕТРЫ ---
if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the PyInstaller bootloader
    # sets the sys.frozen attribute and this points to the executable directory
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

RESOURCE_DIR = os.path.join(BASE_DIR, "data")  # Directory containing all required resources
CSV_FILE = os.path.join(RESOURCE_DIR, "name and numbers.csv")  # Файл с данными
TEMPLATE_PATH = os.path.join(RESOURCE_DIR, "vcard.face.png")  # Файл шаблона визитки
FONT_PATH = os.path.join(RESOURCE_DIR, "font.ttf")  # Файл шрифта
FONT_SIZE_MAX = 300  # Максимальный размер шрифта
CARD_WIDTH = 90 * mm  # Размер визитки
CARD_HEIGHT = 50 * mm
TEXT_MARGIN = 5 * mm  # Отступ от краев
X_POSITIONS = [15 * mm, 106 * mm]  # Позиции карточек в строке
Y_START = 240 * mm  # Верхний край для первой строки
Y_STEP = 51 * mm  # Шаг вниз

# --- ФУНКЦИИ ---

def parse_arguments():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(description='Генератор визитных карточек')
    parser.add_argument('-debug', action='store_true', 
                       help='Включить подробное логирование')
    return parser.parse_args()

def setup_logging(debug_mode):
    """Настройка логирования в зависимости от режима работы"""
    log_filename = f"vcard_generator_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Настраиваем корневой логгер
    logging.getLogger().setLevel(logging.DEBUG if debug_mode else logging.INFO)
    
    # Форматтер для подробного вывода
    debug_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    # Форматтер для простого вывода
    simple_formatter = logging.Formatter('%(message)s')
    
    # Файловый обработчик (всегда с подробным выводом)
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(debug_formatter)
    
    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    console_handler.setFormatter(debug_formatter if debug_mode else simple_formatter)
    
    # Очищаем существующие обработчики и добавляем новые
    logging.getLogger().handlers = []
    logging.getLogger().addHandler(file_handler)
    logging.getLogger().addHandler(console_handler)
    
    return log_filename

def load_data(csv_file):
    """Загружает данные из CSV-файла"""
    logging.info(f"Попытка загрузки данных из файла: {csv_file}")
    if not os.path.exists(csv_file):
        error_msg = f"CSV файл не найден: {csv_file}"
        logging.error(error_msg)
        raise FileNotFoundError(error_msg)
    try:
        data = []
        with open(csv_file, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            for row in reader:
                if len(row) == 3:
                    if not row[0].strip().startswith("#"):
                        data.append((row[0].strip(), row[1].strip(), row[2].strip()))
        logging.info(f"Успешно загружено {len(data)} записей")
        return header, data
    except Exception as e:
        logging.error(f"Ошибка при чтении CSV файла: {str(e)}")
        raise


def calculate_check_digit(number):
    """Вычисляет контрольную цифру для EAN-13"""
    sum_odd = sum(int(digit) for digit in number[::2])
    sum_even = sum(int(digit) for digit in number[1::2])
    check_digit = (10 - (sum_odd + 3 * sum_even) % 10) % 10
    return str(check_digit)


def generate_barcode(number, filename):
    """Генерирует штрихкод EAN-13"""
    logging.info(f"Генерация штрихкода для номера: {number}")
    try:
        if len(number) > 12:
            number = number[:12]
        elif len(number) < 12:
            number += ''.join(random.choices('0123456789', k=12 - len(number)))
        number += calculate_check_digit(number)
        
        # Создаем свой класс writer с отключенным текстом
        options = {
            "module_width": 0.4,
            "module_height": 10,
            "quiet_zone": 3,
            "font_size": 0,  # Устанавливаем размер шрифта в 0, чтобы отключить текст
            "text_distance": 0,  # Устанавливаем расстояние текста в 0
            "write_text": False  # Отключаем отрисовку текста
        }
        
        ean = barcode.get_barcode_class("ean13")
        ean_code = ean(number, writer=ImageWriter())
        path = ean_code.save(filename, options=options)
        
        logging.info(f"Штрихкод успешно создан: {path}")
        return path
        
    except Exception as e:
        logging.error(f"Ошибка при генерации штрихкода: {str(e)}\n{traceback.format_exc()}")
        raise


def fit_text(draw, text, max_width, max_height):
    """Подбирает размер шрифта, чтобы текст уместился"""
    font_size = FONT_SIZE_MAX
    font = ImageFont.truetype(FONT_PATH, font_size)

    while True:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        if text_width <= max_width and text_height <= max_height:
            break
        font_size -= 1
        font = ImageFont.truetype(FONT_PATH, font_size)

    return font


def create_front_card(name, number, additional_info, output_filename):
    """Создает изображение лицевой стороны визитки"""
    logging.info(f"Создание лицевой стороны для: {name}")
    
    try:
        if not os.path.exists(TEMPLATE_PATH):
            error_msg = f"Файл шаблона не найден: {TEMPLATE_PATH}"
            logging.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        if not os.path.exists(FONT_PATH):
            error_msg = f"Файл шрифта не найден: {FONT_PATH}"
            logging.error(error_msg)
            raise FileNotFoundError(error_msg)

        template = Image.open(TEMPLATE_PATH).convert("RGBA")
        logging.debug(f"Шаблон загружен, размер: {template.size}")
        
        draw = ImageDraw.Draw(template)

        # Извлекаем второе слово из имени
        second_word = name.split()[1] if len(name.split()) > 1 else name

        # Определяем максимальную область для текста
        max_width = template.width - 2 * int(TEXT_MARGIN / mm * template.width / CARD_WIDTH)
        max_height = template.height // 3

        # Используем начальный размер шрифта 200
        font_size = 300
        font = ImageFont.truetype(FONT_PATH, font_size)
        font = fit_text(draw, second_word, max_width - max_width / CARD_WIDTH * 2 * TEXT_MARGIN, max_height)

        bbox = draw.textbbox((0, 0), second_word, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = (template.width - text_width) // 2
        text_y = (template.height - text_height) // 2 + 80

        # Рисуем текст синим цветом
        draw.text((text_x, text_y), second_word, font=font, fill=(57, 171, 226, 255))

        # Добавляем дополнительную информацию в нижний правый угол
        additional_font_size = 100
        additional_font = ImageFont.truetype(FONT_PATH, additional_font_size)
        additional_bbox = draw.textbbox((0, 0), additional_info, font=additional_font)
        additional_text_width = additional_bbox[2] - additional_bbox[0]
        additional_text_height = additional_bbox[3] - additional_bbox[1]
        additional_text_x = template.width - additional_text_width - int(TEXT_MARGIN / mm * template.width / CARD_WIDTH)
        additional_text_y = template.height - additional_text_height - int(TEXT_MARGIN / mm * template.height / CARD_HEIGHT)

        draw.text((additional_text_x, additional_text_y), additional_info, font=additional_font, fill=(57, 171, 226, 255))

        template.save(output_filename)
        logging.info(f"Карточка успешно сохранена: {output_filename}")
        return output_filename
        
    except Exception as e:
        logging.error(f"Ошибка при создании лицевой стороны визитки: {str(e)}\n{traceback.format_exc()}")
        raise


def draw_barcode_card(c, x, y, name, number):
    """Рисует карточку со штрихкодом"""
    try:
        c.setStrokeColorRGB(0, 0, 0)
        c.rect(x, y, CARD_WIDTH, CARD_HEIGHT, fill=0)

        # Используем тот же шрифт и цвет, что и для первой стороны
        font_size = 200
        font = ImageFont.truetype(FONT_PATH, font_size)
        # Подбираем размер шрифта для текста
        draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        font = fit_text(draw, name, CARD_WIDTH - 2 * TEXT_MARGIN, CARD_HEIGHT / 3)
        pdfmetrics.registerFont(TTFont("CustomFont", FONT_PATH))
        c.setFont("CustomFont", font.size)
        c.drawCentredString(x + CARD_WIDTH / 2, y + CARD_HEIGHT - 50, name)

        # Генерируем штрихкод
        barcode_path = generate_barcode(number, f"barcode_{number}.png")
        # Размещаем штрихкод
        barcode_width = (CARD_WIDTH - 20)
        barcode_height = 80
        c.drawImage(barcode_path, x + 10, y + 15, barcode_width, barcode_height, preserveAspectRatio=True, mask="auto")
        
        # Добавляем номер штрихкода под изображением
        c.setFont("CustomFont", 8)  # Устанавливаем маленький размер шрифта для номера
        c.drawCentredString(x + CARD_WIDTH / 2, y + 5, number)
        
    except Exception as e:
        logging.error(f"Ошибка при отрисовке карточки со штрихкодом: {str(e)}\n{traceback.format_exc()}")
        raise


def create_pdf(output_filename, debug_mode):
    """Создает PDF с карточками"""
    if debug_mode:
        logging.info("Начало создания PDF файла")
    
    try:
        header, data = load_data(CSV_FILE)
        
        # Выводим список обрабатываемых карточек
        print("\nСоздание карточек для:")
        for name, number, _ in data:
            print(f"- {name}: {number}")
        print()
        
        c = canvas.Canvas(output_filename, pagesize=A4)
        temp_files = []
        
        if debug_mode:
            logging.info("Создание первой страницы (лицевая сторона)")
        
        logging.info("Создание первой страницы (лицевая сторона)")
        y = Y_START
        for i, (name, number, additional_info) in enumerate(data):
            try:
                x = X_POSITIONS[i % 2]
                front_card_path = create_front_card(name, number, additional_info, f"front_{i}.png")
                temp_files.append(front_card_path)
                c.drawImage(front_card_path, x, y, CARD_WIDTH, CARD_HEIGHT, mask="auto")
                
                if (i + 1) % 2 == 0:
                    y -= (Y_STEP + 1 * mm)
            except Exception as e:
                logging.error(f"Ошибка при обработке карточки {i} ({name}): {str(e)}")
                raise

        c.showPage()
        
        logging.info("Создание второй страницы (штрихкоды)")
        y = Y_START
        for i, (name, number, additional_info) in enumerate(data):
            # Swap the positions of the cards in rows
            x = X_POSITIONS[(i + 1) % 2]
            barcode_path = generate_barcode(number, f"barcode_{number}.png")
            temp_files.append(barcode_path)
            draw_barcode_card(c, x, y, name, number)

            if (i + 1) % 2 == 0:
                y -= (Y_STEP + 1 * mm)  # Добавляем отступ 1 мм между карточками

        c.showPage()
        c.save()
        
        if debug_mode:
            logging.info(f"PDF файл успешно создан: {output_filename}")
        else:
            print(f"\nФайл {output_filename} успешно создан!")
            
        # Удаление временных файлов
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
                logging.debug(f"Удален временный файл: {temp_file}")
            except OSError as e:
                logging.warning(f"Не удалось удалить временный файл {temp_file}: {e}")
                
    except Exception as e:
        if debug_mode:
            logging.error(f"Критическая ошибка при создании PDF: {str(e)}\n{traceback.format_exc()}")
        else:
            print(f"\nОшибка: {str(e)}")
            print(f"Подробности в файле: {log_filename}")
        raise


# --- ГЕНЕРАЦИЯ PDF ---
if __name__ == "__main__":
    try:
        args = parse_arguments()
        log_filename = setup_logging(args.debug)
        
        if args.debug:
            logging.info("Запуск программы в режиме отладки")
        
        # Проверяем наличие всех необходимых ресурсов
        required_files = [
            (CSV_FILE, "CSV файл с данными"),
            (TEMPLATE_PATH, "Шаблон визитки"),
            (FONT_PATH, "Файл шрифта")
        ]
        
        for file_path, description in required_files:
            if not os.path.exists(file_path):
                error_msg = f"Не найден {description}: {file_path}"
                if args.debug:
                    logging.error(error_msg)
                else:
                    print(f"Ошибка: {error_msg}")
                raise FileNotFoundError(error_msg)
        
        create_pdf("cards.pdf", args.debug)
        
        if args.debug:
            logging.info("Программа успешно завершена")
        
    except Exception as e:
        if args.debug:
            logging.critical(f"Программа завершилась с ошибкой: {str(e)}\n{traceback.format_exc()}")
        else:
            print(f"\nПрограмма завершилась с ошибкой.")
            print(f"Для получения подробной информации запустите программу с опцией -debug")
        input("\nНажмите Enter для завершения...")
        sys.exit(1)
