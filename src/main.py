from lib.sift import extract_per_image, build_tracks

IMAGES = [f"TestImages/Box/box{i+1}.png" for i in range(12)]

def main():
    all_data = extract_per_image(IMAGES)
    tracks   = build_tracks(all_data)

    print(f"\nFound {len(tracks)} markers seen in 2+ images\n")
    for marker_id, views in sorted(tracks.items()):
        imgs = sorted(views.keys())
        print(f"  Marker {marker_id:3d} → seen in images {imgs}")
        for img_idx in imgs:
            print(f"             image {img_idx}: {views[img_idx]}")

    # `tracks` is your final output — ready for triangulation later
    return tracks


if __name__ == "__main__":
    main()