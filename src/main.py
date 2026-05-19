from detection.shi_tomasi import get_corners
from lib.grouping import group_points
import cv2
from lib.draw import draw_groups

def main():
    images = [f"TestImages/Box/box{i+1}.png" for i in range(12)]

    for img_path in images:
        image = cv2.imread(img_path)

        corners = get_corners(image)
        groups = group_points(corners)

        # draw grouped points
        vis = draw_groups(image, groups)

        cv2.imshow('Grouped Corners', vis)
        cv2.waitKey(0)

        print(groups)


if __name__ == '__main__':
    main()