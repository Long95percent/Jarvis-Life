import sys
from PIL import Image, UnidentifiedImageError

def main():
    if len(sys.argv) < 3:
        print("Usage: python normalize_icon.py <src_image> <dest_ico>")
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2]
    try:
        im = Image.open(src)
        if im.mode not in ("RGBA", "RGB"):
            im = im.convert("RGBA")
        sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
        im.save(dst, format="ICO", sizes=sizes)
        print(f"ICO written: {dst}")
    except UnidentifiedImageError as e:
        print(f"Failed to open image: {e}")
        sys.exit(2)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(3)

if __name__ == "__main__":
    main()

