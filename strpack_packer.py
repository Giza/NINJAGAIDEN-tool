import struct
import csv
import os
import argparse
from pathlib import Path

def align_to_16(offset):
    return (offset + 15) & ~15

def pack_strpack_data(input_csv, output_file, template_file):
    # Читаем тексты из CSV
    texts = []
    with open(input_csv, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts.append(row['text'])
    
    # Читаем шаблонный файл
    with open(template_file, 'rb') as f:
        template_data = f.read()
    
    # Создаем новый файл сразу
    with open(output_file, 'wb') as out_file:
        # Сначала записываем первые 224 байта из шаблона
        out_file.write(template_data[:224])
        
        # Сохраняем позицию для последующей записи таблиц STRPACK
        strpack_tables_pos = out_file.tell()
        
        # Временно пропускаем место под таблицы STRPACK (запишем их позже)
        # Найдем все STRPACK блоки сначала
        strpack_positions = []
        strpack_sizes = []
        pattern = b'STRPACK'
        pos = 0
        while True:
            strpack_offset = template_data.find(pattern, pos)
            if strpack_offset == -1:
                break
            strpack_positions.append(strpack_offset)
            # Читаем размер STRPACK блока
            size_pos = strpack_offset + 16
            size = struct.unpack('<I', template_data[size_pos:size_pos + 4])[0]
            strpack_sizes.append(size)
            pos = strpack_offset + size

        # Вычисляем размер таблиц STRPACK
        strpack_count = len(strpack_positions)
        tables_size = align_to_16(strpack_count * 4) * 2  # Размер для таблицы оффсетов и размеров
        
        # Пропускаем место под таблицы
        out_file.write(b'\x00' * tables_size)
        
        # Ищем все вхождения STRPACK для основной обработки
        current_pos = 0
        last_written_pos = 224 + tables_size  # Начинаем после таблиц STRPACK
        current_text_index = 0
        new_strpack_positions = []  # Для хранения новых позиций STRPACK
        new_strpack_sizes = []      # Для хранения новых размеров STRPACK
        
        while True:
            strpack_offset = template_data.find(pattern, current_pos)
            if strpack_offset == -1:
                # Записываем оставшиеся данные
                out_file.write(template_data[last_written_pos:])
                break

            print(f"STRPACK found at offset: {hex(strpack_offset)}")
            
            # Сохраняем новую позицию STRPACK
            new_strpack_positions.append(out_file.tell()-128)
            
            # Записываем данные до STRPACK
            out_file.write(template_data[last_written_pos:strpack_offset])
            
            # Устанавливаем базовый оффсет
            base_offset = strpack_offset
            current_pos = base_offset + 16
            
            # Записываем STRPACK и заголовок
            out_file.write(template_data[base_offset:current_pos])
            
            # Позиция для записи file_size
            file_size_pos = out_file.tell()

            # Читаем основные параметры
            file_size = struct.unpack('<I', template_data[current_pos:current_pos + 4])[0]
            current_pos += 4
            
            offset_table_count = struct.unpack('<I', template_data[current_pos:current_pos + 4])[0]
            current_pos += 4
            
            size_table_count = struct.unpack('<I', template_data[current_pos:current_pos + 4])[0]
            current_pos += 4
            
            print(f"Количество текстов в этом блоке: {offset_table_count}")
            
            if current_text_index + offset_table_count > len(texts):
                raise ValueError(f"Недостаточно текстов в CSV файле. Нужно {offset_table_count} текстов для блока, но осталось только {len(texts) - current_text_index}")
            
            # Записываем прочитанные параметры
            out_file.write(template_data[current_pos - 12:current_pos])
            
            current_pos += 4  # Пропускаем 4 байта
            out_file.write(template_data[current_pos - 4:current_pos])
            
            offset_table_start = struct.unpack('<I', template_data[current_pos:current_pos + 4])[0]
            current_pos += 4
            
            size_table_start = struct.unpack('<I', template_data[current_pos:current_pos + 4])[0]
            current_pos += 4
            
            # Записываем таблицы начала
            out_file.write(template_data[current_pos - 8:current_pos])
            
            # Записываем оставшиеся 56 байт заголовка
            current_pos += 56
            out_file.write(template_data[current_pos - 56:current_pos])
            
            # Позиция для записи таблицы оффсетов
            offsets_pos = current_pos
            
            # Создаем временный буфер для таблиц
            tables_buffer = bytearray()
            
            # Пропускаем таблицу оффсетов в исходном файле
            current_pos += offset_table_count * 4
            
            # Выравнивание до 16 байт
            current_pos = align_to_16(current_pos)
            
            # Позиция для записи таблицы размеров
            sizes_pos = current_pos
            
            # Пропускаем таблицу размеров в исходном файле
            current_pos += size_table_count * 4
            current_pos = align_to_16(current_pos)
            
            # Начинаем записывать новые тексты и обновлять таблицы
            text_start_pos = current_pos
            new_offsets = []
            new_sizes = []
            text_buffer = bytearray()
            
            # Подготавливаем тексты и собираем информацию
            current_text_pos = current_pos
            # Берем только нужное количество текстов для этого блока
            block_texts = texts[current_text_index:current_text_index + offset_table_count]
            current_text_index += offset_table_count  # Увеличиваем индекс для следующего блока
            
            for text in block_texts:
                # Конвертируем текст в UTF-16-LE и добавляем нулевой байт
                encoded_text = text.encode('utf-16-le') + b'\x00\x00'
                
                # Вычисляем оффсет относительно начала STRPACK
                relative_offset = current_text_pos - base_offset
                new_offsets.append(relative_offset)
                new_sizes.append(len(encoded_text))
                
                # Добавляем текст в буфер
                text_buffer.extend(encoded_text)
                padding_size = align_to_16(len(encoded_text)) - len(encoded_text)
                text_buffer.extend(b'\x00' * padding_size)
                
                current_text_pos += len(encoded_text) + padding_size
            
            # Создаем таблицы оффсетов и размеров
            for offset in new_offsets:
                tables_buffer.extend(struct.pack('<I', offset))
            
            # Выравнивание после таблицы оффсетов
            padding_size = align_to_16(len(tables_buffer)) - len(tables_buffer)
            tables_buffer.extend(b'\x00' * padding_size)
            
            # Добавляем таблицу размеров
            for size in new_sizes:
                tables_buffer.extend(struct.pack('<I', size))
            
            # Выравнивание после таблицы размеров
            padding_size = align_to_16(len(tables_buffer)) - len(tables_buffer)
            tables_buffer.extend(b'\x00' * padding_size)
            
            # Записываем таблицы
            out_file.write(tables_buffer)
            
            # Записываем тексты
            out_file.write(text_buffer)

            # Вычисляем новый размер STRPACK блока
            new_file_size = (current_text_pos - base_offset)
            new_file_size = align_to_16(new_file_size)  # Выравниваем до 16 байт
            
            # Возвращаемся назад и записываем правильный размер файла
            current_file_pos = out_file.tell()
            out_file.seek(file_size_pos)
            out_file.write(struct.pack('<I', new_file_size))
            out_file.seek(current_file_pos)
            
            # После записи блока сохраняем его новый размер
            new_strpack_sizes.append(new_file_size)
            
            # Обновляем позицию для следующей итерации
            current_pos = base_offset + file_size
            last_written_pos = current_pos
            
            print(f"Записан блок STRPACK с {len(block_texts)} текстами, следующая позиция: {hex(current_pos)}")
        
        # Возвращаемся к началу файла и записываем таблицы STRPACK
        out_file.seek(strpack_tables_pos)
        
        # Записываем таблицу оффсетов STRPACK
        for offset in new_strpack_positions:
            out_file.write(struct.pack('<I', offset))
        
        # Выравнивание после таблицы оффсетов
        current_pos = out_file.tell()
        padding_size = align_to_16(current_pos - strpack_tables_pos) - (current_pos - strpack_tables_pos)
        out_file.write(b'\x00' * padding_size)
        
        # Записываем таблицу размеров STRPACK
        for size in new_strpack_sizes:
            out_file.write(struct.pack('<I', size))
            
        # Выравнивание после таблицы размеров
        current_pos = out_file.tell()
        padding_size = align_to_16(current_pos - strpack_tables_pos) - (current_pos - strpack_tables_pos)
        out_file.write(b'\x00' * padding_size)
        
        # Получаем общий размер файла
        out_file.seek(0, 2)  # Переходим в конец файла для получения полного размера
        total_file_size = out_file.tell()
        
        # Вычисляем общий размер STRPACK блоков + 256 байт
        total_strpack_size = sum(new_strpack_sizes) + 256
        
        # Записываем общий размер файла в позицию 16
        out_file.seek(16)
        out_file.write(struct.pack('<I', total_file_size))
        
        # Записываем общий размер STRPACK + 128 в позицию 112
        out_file.seek(112)
        out_file.write(struct.pack('<I', total_strpack_size))
        
        # Записываем общий размер STRPACK + 128 в позицию 144
        out_file.seek(144)
        out_file.write(struct.pack('<I', total_strpack_size))
        
        if current_text_index < len(texts):
            print(f"Предупреждение: не все тексты из CSV были использованы. Осталось {len(texts) - current_text_index} текстов")
        
        print(f"Общий размер файла: {hex(total_file_size)}")
        print(f"Общий размер STRPACK + 256: {hex(total_strpack_size)}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Упаковывает текстовые данные в STRPACK структуры')
    parser.add_argument('input_csv', help='Путь к входному CSV файлу с текстами')
    parser.add_argument('template_file', help='Путь к шаблонному бинарному файлу')
    parser.add_argument('output_file', help='Путь для сохранения упакованного файла')
    
    args = parser.parse_args()
    
    pack_strpack_data(args.input_csv, args.output_file, args.template_file)
    print(f"Упаковка завершена. Результат сохранен в {args.output_file}")