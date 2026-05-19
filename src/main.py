from lib.sift import extract_per_image, build_tracks
from lib.trianulacija import parse_camera_file, triangulate_track

# IMAGES = [f"TestImages/Entrance/entrance{i+1}.png" for i in range(12)]
IMAGES = [f"TestImages/Box/box{i+1}.png" for i in range(12)]

def main():
    cameras = parse_camera_file('TestImages/Box/boxInput.txt')
    all_data = extract_per_image(IMAGES)
    tracks   = build_tracks(all_data)

    with open('output_points.csv', 'w') as f:
        for marker_id, views in sorted(tracks.items()):
            pt, err = triangulate_track(views, cameras)
            if pt is not None:
                f.write(f"{pt[0]:.6f},{pt[1]:.6f},{pt[2]:.6f},255,255,255\n")

    return tracks

if __name__ == "__main__":
    main()
    print("Done :)")