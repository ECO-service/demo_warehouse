import chardet
import subprocess  # Thêm dòng này

# Mở file trong chế độ nhị phân
with open('requirements.txt', 'rb') as f:
    rawdata = f.read()

# Phát hiện mã hóa
result = chardet.detect(rawdata)
encoding = result['encoding']

# Đọc file với mã hóa phát hiện được
with open('requirements.txt', 'r', encoding=encoding) as f:
    packages = f.readlines()

for package in packages:
    package = package.strip()
    try:
        subprocess.run(['pip', 'install', package], check=True)
    except subprocess.CalledProcessError:
        print(f"Failed to install {package}, skipping.")
