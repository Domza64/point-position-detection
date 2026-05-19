import numpy as np
import cv2

def get_corners(image) -> list[tuple[int, int]]:
    # print(img_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Shi-Tomasi corner detection
    corners = cv2.goodFeaturesToTrack(gray, 50, 0.15, 10)
    corners = np.int_(corners)

    return [corner.ravel() for corner in corners]
