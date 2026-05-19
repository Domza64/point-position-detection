from detection.shi_tomasi import get_corners

def main():
    images = [f"TestImages/Box/box{i+1}.png" for i in range(12)]

    for img in images:
        corners = get_corners(img)
        print(corners)


if __name__ == '__main__':
    main()