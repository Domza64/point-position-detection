import cv2
import random

def draw_groups(image, groups):
    """
    Draw each group in a different color.
    """

    output = image.copy()

    # generate stable colors per group
    colors = []

    for _ in range(len(groups)):
        colors.append((
            random.randint(50, 255),
            random.randint(50, 255),
            random.randint(50, 255)
        ))

    for gi, group in enumerate(groups):
        color = colors[gi]

        for pt in group:
            x, y = pt
            cv2.circle(output, (int(x), int(y)), 4, color, -1)

    return output