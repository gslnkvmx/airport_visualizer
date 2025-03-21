import math
import ast

# 1. Открываем файлы POINT.txt и WAY.txt из папки data
point_file_path = "data/POINT.txt"
way_file_path = "data/WAY.txt"

# 2. Читаем файл POINT.txt и создаём словарь координат точек
points_dict = {}
with open(point_file_path, 'r') as pf:
    for line in pf:
        line = line.strip()
        if not line:
            continue  # пропускаем пустые строки
        if line.endswith(','):
            line = line[:-1]  # убираем запятую в конце строки, если есть
        # Преобразуем строку в словарь с помощью ast.literal_eval
        point_data = ast.literal_eval(line)
        point_name = point_data['point']
        points_dict[point_name] = (point_data['x'], point_data['y'])

# 3. Читаем файл WAY.txt и обрабатываем каждую запись маршрута
ways_list = []
with open(way_file_path, 'r') as wf:
    for line in wf:
        line = line.strip()
        if not line:
            continue
        if line.endswith(','):
            line = line[:-1]
        way_data = ast.literal_eval(line)
        ways_list.append(way_data)

# 4. Для каждого маршрута находим координаты точек и вычисляем расстояние
result_records = []
for way in ways_list:
    p1_name = way['point1']
    p2_name = way['point2']
    # Получаем координаты точек p1 и p2 из словаря points_dict
    x1, y1 = points_dict.get(p1_name, (None, None))
    x2, y2 = points_dict.get(p2_name, (None, None))
    if x1 is None or x2 is None:
        # Если точка не найдена в словаре координат, пропускаем эту запись
        continue
    # Вычисляем расстояние по формуле гипотенузы
    dx = x2 - x1
    dy = y2 - y1
    distance = math.sqrt(dx**2 + dy**2)
    distance = round(distance, 1)  # округляем до одного знака после запятой

    # 5. Формируем словарь с результатом для текущего маршрута
    record = {
        'way': way['way'],
        'p1': p1_name,
        'p2': p2_name,
        'x1': x1,
        'y1': y1,
        'x2': x2,
        'y2': y2,
        'len': distance
    }
    result_records.append(record)

# 6. Записываем новый массив записей в файл way2.txt
output_path = "data/way2.txt"
with open(output_path, 'w') as out_file:
    for i, rec in enumerate(result_records):
        out_file.write(str(rec))
        # Добавляем запятую и перевод строки после каждой записи, кроме последней
        if i != len(result_records) - 1:
            out_file.write(',\n')
        else:
            out_file.write('\n')
