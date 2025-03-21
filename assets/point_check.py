import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Load the image
img = plt.imread('map.png')

# Create a figure and axis
fig, ax = plt.subplots()
ax.imshow(img)

# Hide axes
ax.axis('off')

# Define the click event function
def onclick(event):
    if event.xdata is not None and event.ydata is not None:
        print(f'x: {event.xdata:.2f}, y: {event.ydata:.2f}')

# Connect the click event to the function
cid = fig.canvas.mpl_connect('button_press_event', onclick)

# Show the plot
plt.tight_layout()
plt.show()