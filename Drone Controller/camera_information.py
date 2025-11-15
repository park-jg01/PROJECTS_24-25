import os
import exifread

# 네 이미지 폴더 경로
IMAGE_FOLDER = r"C:\Users\DESKTOP-0319\OneDrive_DAEJIN\Document\Meshroom\41"

def extract_exif_info(image_path):
    with open(image_path, 'rb') as f:
        tags = exifread.process_file(f, details=False)

    model = tags.get("Image Model", "N/A")
    lens_model = tags.get("EXIF LensModel", "N/A")
    focal_length = tags.get("EXIF FocalLength", "N/A")

    return {
        "filename": os.path.basename(image_path),
        "model": str(model),
        "lens_model": str(lens_model),
        "focal_length": str(focal_length),
    }

print(f"{'파일명':30} {'Model':40} {'FocalLength':15} {'LensModel'}")
print("=" * 100)

for file in os.listdir(IMAGE_FOLDER):
    if file.lower().endswith((".jpg", ".jpeg")):
        full_path = os.path.join(IMAGE_FOLDER, file)
        info = extract_exif_info(full_path)
        print(f"{info['filename']:30} {info['model']:40} {info['focal_length']:15} {info['lens_model']}")
