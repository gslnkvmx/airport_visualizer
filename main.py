import pygame
import threading
import queue
import pika
import logging
import comands  # импортируем функции и глобальные переменные из comands.py
import time

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URL для подключения к RabbitMQ
RABBITMQ_URL = "amqp://xnyyznus:OSOOLzaQHT5Ys6NPEMAU5DxTChNu2MUe@hawk.rmq.cloudamqp.com:5672/xnyyznus"


def console_input_thread(input_queue):
    """Поток, который ждёт ввода из консоли."""
    while True:
        user_input = input()
        input_queue.put(user_input)


def rabbitmq_listener(input_queue):
    """Поток для прослушивания RabbitMQ-очередей render.move и render.init.
    Полученные сообщения помещаются в input_queue.
    """
    while True:  # Бесконечный цикл для переподключения
        try:
            parameters = pika.URLParameters(RABBITMQ_URL)
            parameters.heartbeat = 600  # Увеличиваем время heartbeat до 10 минут
            parameters.blocked_connection_timeout = 300  # Таймаут для блокированных соединений
            parameters.retry_delay = 5  # Задержка между попытками подключения
            
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            
            # Объявляем очереди (durable=True для устойчивости)
            channel.queue_declare(queue="render.move", durable=False)
            channel.queue_declare(queue="render.init", durable=False)

            def callback(ch, method, properties, body):
                try:
                    message = body.decode("utf-8")
                    logger.info(f"Получено сообщение из RabbitMQ: {message}")
                    input_queue.put(message)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    logger.error(f"Ошибка в callback: {e}")
                    # Не роняем поток при ошибке обработки сообщения
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

            # Устанавливаем prefetch_count=1, чтобы не перегружать очередь
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue="render.move", on_message_callback=callback)
            channel.basic_consume(queue="render.init", on_message_callback=callback)
            
            logger.info("RabbitMQ listener запущен, ожидаем сообщений...")
            channel.start_consuming()
            
        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"Ошибка подключения к RabbitMQ: {e}")
            logger.info("Попытка переподключения через 5 секунд...")
            time.sleep(5)  # Ждём 5 секунд перед повторной попыткой
            continue
            
        except pika.exceptions.AMQPChannelError as e:
            logger.error(f"Ошибка канала RabbitMQ: {e}")
            logger.info("Попытка переподключения через 5 секунд...")
            time.sleep(5)
            continue
            
        except Exception as e:
            logger.error(f"Неожиданная ошибка в RabbitMQ listener: {e}")
            logger.info("Попытка переподключения через 5 секунд...")
            time.sleep(5)
            continue


def main():
    pygame.init()

    # --- 1) Определяем разрешение экрана ---
    info = pygame.display.Info()
    screen_w, screen_h = info.current_w, info.current_h
    print("Разрешение экрана:", screen_w, "x", screen_h)

    # --- 2) Загружаем карту ---
    try:
        raw_map_image = pygame.image.load("assets/map.png")
    except Exception as e:
        print("Ошибка загрузки карты:", e)
        return

    map_width, map_height = raw_map_image.get_width(), raw_map_image.get_height()
    print("Исходный размер карты:", map_width, "x", map_height)

    # --- 3) Вычисляем масштаб ---
    scale = min(
        (screen_w * 0.9) / map_width,
        (screen_h * 0.9) / map_height,
        1.0
    )
    scaled_map_width = int(map_width * scale)
    scaled_map_height = int(map_height * scale)
    print("Итоговый размер карты:", scaled_map_width, "x", scaled_map_height)
    print("Масштаб:", scale)

    # --- 4) Создаём окно ---
    screen = pygame.display.set_mode((scaled_map_width, scaled_map_height))
    pygame.display.set_caption("Airport Visualizer")

    # Масштабируем карту
    map_image = pygame.transform.smoothscale(raw_map_image, (scaled_map_width, scaled_map_height)).convert()

    clock = pygame.time.Clock()

    # --- 5) Создаём общую очередь команд ---
    input_queue = queue.Queue()

    # --- 6) Запускаем поток консольного ввода ---
    console_thread = threading.Thread(target=console_input_thread, args=(input_queue,), daemon=True)
    console_thread.start()

    # --- 7) Запускаем RabbitMQ listener в отдельном потоке ---
    rabbit_thread = threading.Thread(target=rabbitmq_listener, args=(input_queue,), daemon=True)
    rabbit_thread.start()

    # --- 8) Масштабирование изображений для /plane и /car ---
    plane_factor = 0.2
    if comands.plane_image_original:
        w_orig, h_orig = comands.plane_image_original.get_size()
        new_w = int(w_orig * scale * plane_factor)
        new_h = int(h_orig * scale * plane_factor)
        new_w = max(new_w, 1)
        new_h = max(new_h, 1)
        comands.plane_image_scaled = pygame.transform.smoothscale(comands.plane_image_original, (new_w, new_h))
        print(f"Самолёт после масштабирования: {new_w}x{new_h}")
    else:
        print("Предупреждение: plane_image_original ещё не загружен в comands.py")

    car_factor = 0.1  # Машина должна быть в 2 раза меньше самолёта
    for model, orig_image in comands.car_images_original.items():
        if comands.car_images_scaled.get(model) is None:
            w_orig, h_orig = orig_image.get_size()
            new_w = int(w_orig * scale * car_factor)
            new_h = int(h_orig * scale * car_factor)
            new_w = max(new_w, 1)
            new_h = max(new_h, 1)
            comands.car_images_scaled[model] = pygame.transform.smoothscale(orig_image, (new_w, new_h))
            print(f"Машина {model} после масштабирования: {new_w}x{new_h}")

    action_factor = 0.25  # Коэффициент для GIF-анимаций /action

    running = True
    while running:
        # --- Обработка событий Pygame ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        # --- Обработка команд из общей очереди ---
        while not input_queue.empty():
            cmd_line = input_queue.get()
            if cmd_line.startswith("/"):
                parts = cmd_line.split()
                if parts[0] == "/way":
                    route = comands.command_way(parts[1:])
                    print("Маршрут:", route if route else "Не найден.")
                elif parts[0] == "/plane":
                    route = comands.command_plane(parts[1:])
                    if route:
                        print("Маршрут самолёта:", route)
                        if (comands.plane_image_original and comands.plane_image_scaled is None):
                            w_orig, h_orig = comands.plane_image_original.get_size()
                            new_w = int(w_orig * scale * plane_factor)
                            new_h = int(h_orig * scale * plane_factor)
                            new_w = max(new_w, 1)
                            new_h = max(new_h, 1)
                            comands.plane_image_scaled = pygame.transform.smoothscale(comands.plane_image_original,
                                                                                      (new_w, new_h))
                elif parts[0] == "/car":
                    route = comands.command_car(parts[1:])
                    if route:
                        print("Маршрут машины:", route)
                        car_id = parts[1]
                        model = comands.get_car_model_from_id(car_id)
                        if model and model in comands.car_images_original and comands.car_images_scaled.get(model) is None:
                            orig_image = comands.car_images_original[model]
                            w_orig, h_orig = orig_image.get_size()
                            new_w = int(w_orig * scale * car_factor)
                            new_h = int(h_orig * scale * car_factor)
                            new_w = max(new_w, 1)
                            new_h = max(new_h, 1)
                            comands.car_images_scaled[model] = pygame.transform.smoothscale(orig_image, (new_w, new_h))
                elif parts[0] == "/action":
                    # Новая команда /action <Name> <Point>
                    comands.command_action(parts[1:])
                elif parts[0] == "/move":
                    route = comands.command_move(parts[1:])
                    if route:
                        print("Маршрут:", route)
                        vehicle_type, vehicle_number = comands.get_vehicle_type_from_id(parts[1])
                        
                        if vehicle_type == "car":
                            model = vehicle_number
                            if model in comands.car_images_original and comands.car_images_scaled.get(model) is None:
                                orig_image = comands.car_images_original[model]
                                w_orig, h_orig = orig_image.get_size()
                                new_w = int(w_orig * scale * car_factor)
                                new_h = int(h_orig * scale * car_factor)
                                new_w = max(new_w, 1)
                                new_h = max(new_h, 1)
                                comands.car_images_scaled[model] = pygame.transform.smoothscale(orig_image, (new_w, new_h))
                        elif vehicle_type == "plane":
                            if comands.plane_image_original and comands.plane_image_scaled is None:
                                w_orig, h_orig = comands.plane_image_original.get_size()
                                new_w = int(w_orig * scale * plane_factor)
                                new_h = int(h_orig * scale * plane_factor)
                                new_w = max(new_w, 1)
                                new_h = max(new_h, 1)
                                comands.plane_image_scaled = pygame.transform.smoothscale(comands.plane_image_original, (new_w, new_h))
                elif parts[0] == "/init":
                    point = comands.command_init(parts[1:])
                    if point:
                        print(f"Техника инициализирована на точке {point}")
                        vehicle_type, vehicle_number = comands.get_vehicle_type_from_id(parts[1])
                        
                        if vehicle_type == "car":
                            model = vehicle_number
                            if model in comands.car_images_original and comands.car_images_scaled.get(model) is None:
                                orig_image = comands.car_images_original[model]
                                w_orig, h_orig = orig_image.get_size()
                                new_w = int(w_orig * scale * car_factor)
                                new_h = int(h_orig * scale * car_factor)
                                new_w = max(new_w, 1)
                                new_h = max(new_h, 1)
                                comands.car_images_scaled[model] = pygame.transform.smoothscale(orig_image, (new_w, new_h))
                        elif vehicle_type == "plane":
                            if comands.plane_image_original and comands.plane_image_scaled is None:
                                w_orig, h_orig = comands.plane_image_original.get_size()
                                new_w = int(w_orig * scale * plane_factor)
                                new_h = int(h_orig * scale * plane_factor)
                                new_w = max(new_w, 1)
                                new_h = max(new_h, 1)
                                comands.plane_image_scaled = pygame.transform.smoothscale(comands.plane_image_original, (new_w, new_h))
                elif parts[0] == "/clear":
                    removed = comands.command_clear(parts[1:])
                    if removed is not None:
                        print(f"Команда очистки выполнена успешно")
                else:
                    print("Неизвестная команда")
            else:
                print("не команда")

        # --- Отрисовка карты ---
        screen.blit(map_image, (0, 0))

        # --- Отрисовка самолётов (/plane) ---
        for plane_id, plane_data in list(comands.planes.items()):
            route = plane_data.get("route", [])
            idx = plane_data.get("route_index", 1)
            if idx < len(route):
                current_vertex = route[idx - 1]
                target_vertex = route[idx]
                
                # Если текущая или целевая точка - ребро, используем его середину
                if comands.is_edge(current_vertex):
                    current_pos = comands.get_edge_midpoint(current_vertex) or (plane_data["x"], plane_data["y"])
                else:
                    current_pos = comands.point_coords.get(current_vertex, (plane_data["x"], plane_data["y"]))
                    
                if comands.is_edge(target_vertex):
                    target_pos = comands.get_edge_midpoint(target_vertex) or current_pos
                else:
                    target_pos = comands.point_coords.get(target_vertex, current_pos)
                
                dx = target_pos[0] - plane_data["x"]
                dy = target_pos[1] - plane_data["y"]
                dist = (dx ** 2 + dy ** 2) ** 0.5

                if dist < plane_data["speed"]:
                    plane_data["x"], plane_data["y"] = target_pos
                    plane_data["route_index"] += 1
                    plane_data["current_node"] = target_vertex
                    # Проверяем, достиг ли самолёт точки RW-0
                    if target_vertex == "RW-0":
                        plane_data["removing"] = True
                else:
                    plane_data["x"] += plane_data["speed"] * dx / dist
                    plane_data["y"] += plane_data["speed"] * dy / dist
                import math
                computed_angle = math.degrees(math.atan2(-dy, dx)) + 180
                # Сохраняем последний расчитанный угол
                plane_data["last_angle"] = computed_angle
            else:
                if plane_data.get("removing", False):
                    del comands.planes[plane_id]
                    continue
                # Используем последний сохраненный угол вместо нуля
                computed_angle = plane_data.get("last_angle", 0)

            if plane_id in comands.planes:
                draw_x = plane_data["x"] * scale
                draw_y = plane_data["y"] * scale
                if comands.plane_image_scaled:
                    final_angle = computed_angle + plane_data.get("ange", 0)
                    rotated_image = pygame.transform.rotate(comands.plane_image_scaled, final_angle)
                    plane_rect = rotated_image.get_rect()
                    plane_rect.center = (draw_x, draw_y)
                    screen.blit(rotated_image, plane_rect)

        # --- Отрисовка машин (/car) ---
        for car_id, car_data in list(comands.cars.items()):
            model = car_data.get("model")
            route = car_data.get("route", [])
            idx = car_data.get("route_index", 1)
            if idx < len(route):
                current_vertex = route[idx - 1]
                target_vertex = route[idx]
                
                # Если текущая или целевая точка - ребро, используем его середину
                if comands.is_edge(current_vertex):
                    current_pos = comands.get_edge_midpoint(current_vertex) or (car_data["x"], car_data["y"])
                else:
                    current_pos = comands.point_coords.get(current_vertex, (car_data["x"], car_data["y"]))
                    
                if comands.is_edge(target_vertex):
                    target_pos = comands.get_edge_midpoint(target_vertex) or current_pos
                else:
                    target_pos = comands.point_coords.get(target_vertex, current_pos)
                
                dx = target_pos[0] - car_data["x"]
                dy = target_pos[1] - car_data["y"]
                dist = (dx ** 2 + dy ** 2) ** 0.5

                if dist < car_data["speed"]:
                    car_data["x"], car_data["y"] = target_pos
                    car_data["route_index"] += 1
                    car_data["current_node"] = target_vertex
                else:
                    car_data["x"] += car_data["speed"] * dx / dist
                    car_data["y"] += car_data["speed"] * dy / dist
                import math
                computed_angle = math.degrees(math.atan2(-dy, dx)) + 180
            else:
                if route and route[-1] == car_data.get("start_origin"):
                    comands.car_counts[model] -= 1
                    del comands.cars[car_id]
                    continue
                computed_angle = 0

            if car_id in comands.cars:
                draw_x = car_data["x"] * scale
                draw_y = car_data["y"] * scale
                if model in comands.car_images_scaled and comands.car_images_scaled[model]:
                    car_image = comands.car_images_scaled[model]
                    rotated_image = pygame.transform.rotate(car_image, computed_angle)
                    car_rect = rotated_image.get_rect()
                    car_rect.center = (draw_x, draw_y)
                    screen.blit(rotated_image, car_rect)

        # --- Отрисовка анимаций /action ---
        now = pygame.time.get_ticks()
        for action_id, action_data in list(comands.actions.items()):
            start_time = action_data["start_time"]
            duration = action_data["duration"]
            if now - start_time > duration:
                del comands.actions[action_id]
                continue

            name = action_data["name"]
            if name not in comands.action_frames_scaled or comands.action_frames_scaled[name] is None:
                scaled_frames = []
                for frame in comands.action_frames[name]:
                    w_orig, h_orig = frame.get_size()
                    new_w = int(w_orig * scale * action_factor)
                    new_h = int(h_orig * scale * action_factor)
                    new_w = max(new_w, 1)
                    new_h = max(new_h, 1)
                    scaled_frame = pygame.transform.smoothscale(frame, (new_w, new_h))
                    scaled_frames.append(scaled_frame)
                comands.action_frames_scaled[name] = scaled_frames

            elapsed = now - start_time
            frames_list = comands.action_frames[name]
            n_frames = len(frames_list)
            frame_index = int((elapsed / duration) * n_frames)
            if frame_index >= n_frames:
                frame_index = n_frames - 1
            current_frame = comands.action_frames_scaled[name][frame_index]
            draw_x = action_data["x"] * scale
            draw_y = action_data["y"] * scale
            rect = current_frame.get_rect()
            rect.center = (draw_x, draw_y)
            screen.blit(current_frame, rect)

        pygame.display.flip()
        clock.tick(10)

    pygame.quit()


if __name__ == '__main__':
    main()
