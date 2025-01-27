import struct
import csv
import os
import argparse
from pathlib import Path

def align_to_16(offset):
    return (offset + 15) & ~15

def extract_strpack_data(file_path, output_csv):
    texts_data = []
    
    with open(file_path, 'rb') as f:
        data = f.read()
        
    # Поиск всех вхождений STRPACK
    pattern = b'STRPACK'
    current_pos = 0
    
    while True:
        strpack_offset = data.find(pattern, current_pos)
        if strpack_offset == -1:
            break

        print(f"STRPACK found at offset: {hex(strpack_offset)}")

        # Устанавливаем базовый оффсет
        base_offset = strpack_offset
        current_pos = base_offset + 16  # Пропускаем STRPACK и 16 байт
        
        # Чтение основных параметров
        file_size = struct.unpack('<I', data[current_pos:current_pos + 4])[0]
        current_pos += 4
        
        offset_table_count = struct.unpack('<I', data[current_pos:current_pos + 4])[0]
        current_pos += 4
        
        size_table_count = struct.unpack('<I', data[current_pos:current_pos + 4])[0]
        current_pos += 4
        
        current_pos += 4  # Пропускаем 4 байта
        
        offset_table_start = struct.unpack('<I', data[current_pos:current_pos + 4])[0]
        current_pos += 4
        
        size_table_start = struct.unpack('<I', data[current_pos:current_pos + 4])[0]
        current_pos += 4
        
        current_pos += 56  # Пропускаем 56 байт
        
        # Чтение таблицы оффсетов
        offsets_str = []
        for _ in range(offset_table_count):
            offset = struct.unpack('<I', data[current_pos:current_pos + 4])[0]
            offsets_str.append(offset)
            current_pos += 4
            
        # Выравнивание до 16 байт
        current_pos = align_to_16(current_pos)
        
        # Чтение таблицы размеров
        sizes_str = []
        for _ in range(size_table_count):
            size = struct.unpack('<I', data[current_pos:current_pos + 4])[0]
            sizes_str.append(size)
            current_pos += 4
            
        # Чтение текстовых данных
        for offset, size in zip(offsets_str, sizes_str):
            absolute_offset = base_offset + offset
            try:
                text = data[absolute_offset:absolute_offset + size].decode('utf-16-le').rstrip('\x00')
                texts_data.append({
                    'text': text
                })
            except Exception as e:
                print(f"Ошибка при декодировании текста на оффсете {hex(absolute_offset)}: {e}")
        
        current_pos = base_offset + file_size
        
    # Запись данных в CSV
    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['text'])
        writer.writeheader()
        writer.writerows(texts_data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Извлекает текстовые данные из STRPACK структур')
    parser.add_argument('input_file', help='Путь к входному бинарному файлу')
    parser.add_argument('output_csv', help='Путь для сохранения CSV файла')
    
    args = parser.parse_args()
    
    extract_strpack_data(args.input_file, args.output_csv)
    print(f"Обработка завершена. Результаты сохранены в {args.output_csv}") 