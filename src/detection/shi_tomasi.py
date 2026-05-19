import numpy as np
import cv2

def get_corners(img_path: str) -> list[tuple[int, int]]:
    print(img_path)
    # Load image
    image = cv2.imread(img_path)
    # print(img_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Shi-Tomasi corner detection
    corners = cv2.goodFeaturesToTrack(gray, 50, 0.15, 10)
    corners = np.int_(corners)

    # Draw corners
    for corner in corners:
        x, y = corner.ravel()
        cv2.circle(image, (x, y), 1, 255, -1)

    # Show result - Debug
    cv2.imshow('Shi-Tomasi Corners', image)
    cv2.waitKey(0)

    return [corner.ravel() for corner in corners]
