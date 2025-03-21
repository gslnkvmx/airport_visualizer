import matplotlib.pyplot as plt
import ast

# Путь к файлу
file_path = "data/way2.txt"

# Читаем файл и формируем список словарей
with open(file_path, "r") as f:
    content = f.read().strip()

if content.endswith(","):
    content = content.rstrip(",\n")
content = "[" + content + "]"
ways = ast.literal_eval(content)

# Инициализируем график
plt.figure(figsize=(10, 8))

# Рисуем линии для каждого маршрута с маркерами и подписями
for route in ways:
    x1, y1 = route['x1'], route['y1']
    x2, y2 = route['x2'], route['y2']
    plt.plot([x1, x2], [y1, y2], marker='o')
    midx, midy = (x1 + x2) / 2, (y1 + y2) / 2
    plt.text(midx, midy, route['way'], fontsize=8, ha='center', va='center')

plt.xlabel("X")
plt.ylabel("Y")
plt.title("Маршруты из файла way2.txt")
plt.grid(True)

# Инвертируем ось Y для соответствия системе координат Pygame
plt.gca().invert_yaxis()

plt.tight_layout()
plt.show()
