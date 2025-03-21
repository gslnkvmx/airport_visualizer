import pygame
from collections import deque
from ways import ways
from points import points
from PIL import Image  # для работы с GIF

# -------------------- ГЛОБАЛЬНЫЕ ДАННЫЕ --------------------

# Построение неориентированного графа на основе списка путей.
graph = {}
for way in ways:
    a = way.get('p1') or way.get('point1')
    b = way.get('p2') or way.get('point2')
    if a and b:
        graph.setdefault(a, []).append(b)
        graph.setdefault(b, []).append(a)

# Словарь координат точек.
point_coords = {pt['point']: (pt['x'], pt['y']) for pt in points}

# -------------------- ДАННЫЕ ДЛЯ /plane --------------------
planes = {}  # {номер: данные самолёта}
plane_image_original = None  # Исходное изображение самолёта (plane.png)
plane_image_scaled = None  # Масштабированное изображение самолёта

# -------------------- ДАННЫЕ ДЛЯ /car --------------------
# Используем id машины как ключ (например, "BUS-1")
cars = {}  # { car_id: { ... данные машины ... } }
car_images_original = {}  # { model: оригинальное изображение машины }
car_images_scaled = {}  # { model: масштабированное изображение машины }

# Словарь соответствия коротких ID типам машин
VEHICLE_TYPE_MAPPING = {
    "BUS": "bus",
    "BG": "baggage_tractor",
    "CT": "catering_truck",
    "FM": "followme",
    "RT": "fuel_truck"
}

# Обновляем список разрешенных моделей машин
ALLOWED_CAR_MODELS = set(VEHICLE_TYPE_MAPPING.values())

# Словарь для отслеживания количества машин каждого типа
car_counts = {model: 0 for model in ALLOWED_CAR_MODELS}

# -------------------- ДАННЫЕ ДЛЯ /action --------------------
# Словарь активных анимаций. Структура:
# actions[action_id] = {
#    "name": <имя GIF>,
#    "x": <логическая координата>,
#    "y": <логическая координата>,
#    "start_time": <pygame.time.get_ticks() в момент появления>,
#    "duration": 4000   # длительность в мс
# }
actions = {}

# Словарь, в котором для каждого допустимого имени хранится список кадров (Surface)
action_frames = {}
# Словарь для масштабированных кадров (аналог action_frames, но уже с учетом масштаба)
action_frames_scaled = {}

ALLOWED_ACTION_NAMES = {
    "baggage_man",
    "bus_passengers",
    "catering_man",
    "fuel_man"
}


# -------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ --------------------

def load_gif_frames(filename):
    """
    Загружает анимированный GIF из файла и разбивает его на кадры.
    Возвращает список pygame.Surface.
    """
    frames = []
    try:
        with Image.open(filename) as im:
            while True:
                frame = im.convert("RGBA")
                mode = frame.mode
                size = frame.size
                data = frame.tobytes()
                surface = pygame.image.fromstring(data, size, mode).convert_alpha()
                frames.append(surface)
                im.seek(im.tell() + 1)
    except EOFError:
        pass
    return frames


def bfs_path(start, end, graph):
    """
    Поиск кратчайшего пути от start до end с помощью поиска в ширину (BFS).
    Возвращает список вершин или пустой список, если путь не найден.
    """
    queue = deque([start])
    visited = {start}
    prev = {start: None}

    while queue:
        current = queue.popleft()
        if current == end:
            break
        for neighbor in graph.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                prev[neighbor] = current
                queue.append(neighbor)

    if end not in prev:
        return []
    path = []
    cur = end
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path


# -------------------- КОМАНДЫ --------------------

def command_way(parts):
    """
    /way <start> <end>
    Находит маршрут между точками start и end с помощью BFS.
    Возвращает список вершин или пустой список.
    """
    if len(parts) != 2:
        print("Неверный формат команды. Используйте: /way <начало> <конец>")
        return []
    start, goal = parts[0], parts[1]
    if start not in graph:
        print(f"Точка {start} не найдена в графе.")
        return []
    if goal not in graph:
        print(f"Точка {goal} не найдена в графе.")
        return []
    route = bfs_path(start, goal, graph)
    if not route:
        print("Путь не найден.")
    return route


def command_plane(parts):
    """
    /plane <номер>
    Если самолёт с указанным номером уже существует – строит маршрут до RW-0.
    Если самолёта нет, создаёт нового (до 5 одновременно) с маршрутом от RW-0 до свободного гейта.
    """
    if len(parts) != 1:
        print("Неверный формат команды. Используйте: /plane <номер>")
        return None

    try:
        plane_id = int(parts[0])
    except ValueError:
        print("Ошибка: некорректный номер самолёта.")
        return None

    if plane_id in planes:
        plane = planes[plane_id]
        current_node = plane.get('current_node', "RW-0")
        route_to_rw = command_way([current_node, "RW-0"])
        if route_to_rw and route_to_rw[-1] == "RW-0":
            plane['route'] = route_to_rw
            plane['route_index'] = 1
            plane['removing'] = True
        return plane.get('route', [])

    if len(planes) >= 5:
        print("Ошибка: превышен лимит самолётов (максимум 5).")
        return None

    gates_priority = ["P-5", "P-4", "P-3", "P-2", "P-1"]
    occupied_gates = {plane.get('gate') for plane in planes.values() if plane.get('gate')}
    chosen_gate = None
    for gate in gates_priority:
        if gate not in occupied_gates:
            chosen_gate = gate
            break
    if chosen_gate is None:
        print("Ошибка: нет свободных гейтов.")
        return None

    route_to_gate = command_way(["RW-0", chosen_gate])
    if not route_to_gate or route_to_gate[-1] != chosen_gate:
        print(f"Ошибка: маршрут до {chosen_gate} не найден.")
        return None

    x0, y0 = point_coords.get("RW-0", (0, 0))

    global plane_image_original
    if plane_image_original is None:
        try:
            plane_image_original = pygame.image.load("assets/plane.png").convert_alpha()
        except Exception as e:
            print("Ошибка загрузки plane.png:", e)
            return None

    planes[plane_id] = {
        "id": plane_id,
        "x": x0,
        "y": y0,
        "route": route_to_gate,
        "route_index": 1,
        "gate": chosen_gate,
        "removing": False,
        "speed": 10.0,
        "current_node": "RW-0",
        "ange": 0
    }
    return planes[plane_id]['route']


def get_vehicle_type_from_id(vehicle_id):
    """Определяет тип техники по ID.
    Возвращает кортеж (тип, номер):
    - для самолётов: ("plane", номер)
    - для машин: ("car", тип_машины)
    """
    if not vehicle_id or "-" not in vehicle_id:
        return None, None
        
    prefix, number = vehicle_id.split("-", 1)
    prefix = prefix.upper()
    
    if prefix == "PL":
        return "plane", number
    elif prefix in VEHICLE_TYPE_MAPPING:
        return "car", VEHICLE_TYPE_MAPPING[prefix]
    else:
        return None, None


def get_car_model_from_id(car_id):
    """Получает модель машины из её ID."""
    if not car_id or "-" not in car_id:
        return None
        
    prefix = car_id.split("-", 1)[0].upper()
    return VEHICLE_TYPE_MAPPING.get(prefix)


def get_car_current_node(car):
    """
    Определяет текущую вершину, на которой находится машина.
    Если машина движется между точками, возвращает последнюю достигнутую вершину.
    """
    route = car.get("route", [])
    idx = car.get("route_index", 1)
    if not route or idx < 1:
        return None
    if idx >= len(route):
        return route[-1]
    else:
        return route[idx - 1]


def is_edge(point):
    """
    Проверяет, является ли точка ребром (начинается с 'E').
    """
    return isinstance(point, str) and point.startswith('E')


def find_edge_endpoints(edge_name):
    """
    Находит вершины, которые соединяет ребро.
    Возвращает кортеж (vertex1, vertex2) или None, если ребро не найдено.
    """
    for way in ways:
        if way.get('way') == edge_name:
            p1 = way.get('p1') or way.get('point1')
            p2 = way.get('p2') or way.get('point2')
            if p1 and p2:
                return (p1, p2)
    return None


def get_edge_midpoint(edge_name):
    """
    Вычисляет координаты середины ребра.
    Возвращает кортеж (x, y) или None, если ребро не найдено.
    """
    endpoints = find_edge_endpoints(edge_name)
    if not endpoints:
        return None
    
    v1, v2 = endpoints
    if v1 not in point_coords or v2 not in point_coords:
        return None
        
    x1, y1 = point_coords[v1]
    x2, y2 = point_coords[v2]
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def bfs_path_with_edges(start, end, graph):
    """
    Модифицированный поиск пути с поддержкой начала/конца на рёбрах.
    """
    # Если начало или конец - ребро, находим его конечные точки
    start_points = []
    end_points = []
    
    if is_edge(start):
        endpoints = find_edge_endpoints(start)
        if endpoints:
            start_points = list(endpoints)
    else:
        start_points = [start]
        
    if is_edge(end):
        endpoints = find_edge_endpoints(end)
        if endpoints:
            end_points = list(endpoints)
    else:
        end_points = [end]
    
    # Если не удалось найти точки для ребер, возвращаем пустой путь
    if not start_points or not end_points:
        return []
    
    # Находим кратчайший путь между всеми возможными комбинациями точек
    shortest_path = []
    min_length = float('inf')
    
    for s in start_points:
        for e in end_points:
            path = bfs_path(s, e, graph)
            if path and len(path) < min_length:
                min_length = len(path)
                shortest_path = path
                
    # Добавляем ребра в начало и конец пути, если они были указаны
    if shortest_path:
        if is_edge(start):
            shortest_path.insert(0, start)
        if is_edge(end):
            shortest_path.append(end)
            
    return shortest_path


def command_move(parts):
    """
    /move <id> <origin> <destination>

    ID может быть:
    - PL-N для самолётов (например, "PL-1")
    - MODEL-N для машин (например, "BUS-1", "FUEL_TRUCK-2")
    
    Origin и Destination могут быть:
    - Вершинами графа (точками)
    - Рёбрами (E-*) - для всех типов транспорта
    """
    if len(parts) != 3:
        print("Неверный формат команды. Используйте: /move <id> <origin> <destination>")
        return None

    vehicle_id, origin, destination = parts
    vehicle_type, vehicle_number = get_vehicle_type_from_id(vehicle_id)

    if not vehicle_type:
        print(f"Ошибка: некорректный ID '{vehicle_id}'. Должен быть в формате PL-N для самолётов или MODEL-N для машин.")
        return None

    # Проверяем существование точек/рёбер
    if not is_edge(origin) and origin not in graph:
        print(f"Точка {origin} не найдена в графе.")
        return None
    if not is_edge(destination) and destination not in graph:
        print(f"Точка {destination} не найдена в графе.")
        return None
    if is_edge(origin) and not find_edge_endpoints(origin):
        print(f"Ребро {origin} не найдено.")
        return None
    if is_edge(destination) and not find_edge_endpoints(destination):
        print(f"Ребро {destination} не найдено.")
        return None

    # Обработка самолётов
    if vehicle_type == "plane":
        if vehicle_id in planes:
            plane = planes[vehicle_id]
            current_node = plane.get('current_node', origin)
            route = bfs_path_with_edges(current_node, destination, graph)
            if route:
                plane['route'] = route
                plane['route_index'] = 1
                plane['removing'] = False
                return route
        else:
            print(f"Ошибка: самолёт {vehicle_id} не найден. Используйте /init для создания.")
            return None

    # Обработка машин
    else:  # vehicle_type == "car"
        if vehicle_id in cars:
            car = cars[vehicle_id]
            current_node = car.get('current_node', origin)
            route = bfs_path_with_edges(current_node, destination, graph)
            if route:
                car['route'] = route
                car['route_index'] = 1
                return route
            else:
                print("Маршрут не найден.")
                return None
        else:
            print(f"Ошибка: машина {vehicle_id} не найдена. Используйте /init для создания.")
            return None


def command_action(parts):
    """
    /action <Name> <Point>

    - Name: имя анимации (одно из ALLOWED_ACTION_NAMES)
    - Point: вершина карты (должна присутствовать в point_coords)

    После вызова анимация появляется на заданной точке, анимация проигрывается в течение 4 секунд и затем исчезает.
    При первом вызове для данного имени GIF разбивается на кадры с помощью Pillow.
    """
    if len(parts) != 2:
        print("Неверный формат команды. Используйте: /action <Name> <Point>")
        return

    name, point = parts
    if name not in ALLOWED_ACTION_NAMES:
        print(f"Ошибка: '{name}' не является допустимым именем. Допустимые: {ALLOWED_ACTION_NAMES}")
        return

    if point not in point_coords:
        print(f"Ошибка: точка {point} не найдена.")
        return

    x, y = point_coords[point]

    # Загружаем и разбиваем GIF на кадры, если ещё не загружено.
    if name not in action_frames:
        try:
            frames = load_gif_frames(f"animations/{name}.gif")
            if not frames:
                print(f"Не удалось загрузить кадры из GIF '{name}.gif'")
                return
            action_frames[name] = frames
            action_frames_scaled[name] = None  # Масштабирование выполнится в main.py
        except Exception as e:
            print(f"Ошибка загрузки GIF '{name}.gif': {e}")
            return

    # Создаём запись в actions с автоинкрементным ключом.
    action_id = len(actions) + 1
    actions[action_id] = {
        "name": name,
        "x": x,
        "y": y,
        "start_time": pygame.time.get_ticks(),
        "duration": 4000  # 4 секунды
    }

    print(f"Появляется анимация '{name}' на точке {point} (action_id={action_id})")


def command_init(parts):
    """Инициализация техники на указанной точке.
    Формат: /init <id> <point>
    """
    if len(parts) != 2:
        print("Использование: /init <id> <point>")
        return None

    vehicle_id = parts[0]
    point = parts[1]

    # Проверяем, является ли точка node
    if is_edge(point):
        print("Ошибка: нельзя инициализировать технику на ребре")
        return None

    # Проверяем существование точки
    if point not in point_coords:
        print(f"Ошибка: точка {point} не найдена")
        return None

    # Определяем тип техники
    vehicle_type, vehicle_number = get_vehicle_type_from_id(vehicle_id)
    
    if vehicle_type == "plane":
        # Проверяем, не существует ли уже самолёт с таким ID
        if vehicle_id in planes:
            print(f"Ошибка: самолёт {vehicle_id} уже существует")
            return None
            
        # Загружаем изображение самолёта, если ещё не загружено
        global plane_image_original
        if plane_image_original is None:
            try:
                plane_image_original = pygame.image.load("assets/plane.png").convert_alpha()
            except Exception as e:
                print("Ошибка загрузки plane.png:", e)
                return None
            
        # Создаём новый самолёт
        planes[vehicle_id] = {
            "x": point_coords[point][0],
            "y": point_coords[point][1],
            "route": [],
            "route_index": 0,
            "speed": 8.0,
            "current_node": point,
            "last_angle": 0
        }
        print(f"Самолёт {vehicle_id} инициализирован на точке {point}")
        
    elif vehicle_type == "car":
        # Проверяем, не существует ли уже машина с таким ID
        if vehicle_id in cars:
            print(f"Ошибка: машина {vehicle_id} уже существует")
            return None
            
        # Загружаем изображение машины, если ещё не загружено
        if vehicle_number not in car_images_original:
            try:
                car_images_original[vehicle_number] = pygame.image.load(f"assets/{vehicle_number}.png").convert_alpha()
            except Exception as e:
                print(f"Ошибка загрузки {vehicle_number}.png:", e)
                return None
            
        # Создаём новую машину
        cars[vehicle_id] = {
            "model": vehicle_number,
            "x": point_coords[point][0],
            "y": point_coords[point][1],
            "route": [],
            "route_index": 0,
            "speed": 6.0,
            "current_node": point,
            "last_angle": 0
        }
        car_counts[vehicle_number] = car_counts.get(vehicle_number, 0) + 1
        print(f"Машина {vehicle_id} инициализирована на точке {point}")
        
    else:
        print(f"Ошибка: неизвестный тип техники {vehicle_id}")
        return None
        
    return point


def command_clear(parts):
    """Удаление всей техники указанного типа.
    Формат: /clear <тип техники>
    Например: /clear BUS - удалит все автобусы
             /clear PL - удалит все самолёты
    """
    if len(parts) != 1:
        print("Использование: /clear <тип техники>")
        return None

    vehicle_type = parts[0].upper()
    removed_count = 0

    # Удаляем всю технику указанного типа
    if vehicle_type == "PL":
        removed_count = len(planes)
        planes.clear()
        print(f"Удалено самолётов: {removed_count}")
    else:
        # Для остальной техники (BUS, CT, и т.д.)
        to_remove = []
        for car_id in cars:
            if car_id.startswith(vehicle_type):
                to_remove.append(car_id)
                model = cars[car_id]["model"]
                car_counts[model] = max(0, car_counts[model] - 1)
                removed_count += 1
        
        for car_id in to_remove:
            del cars[car_id]
        
        print(f"Удалено техники типа {vehicle_type}: {removed_count}")

    return removed_count
