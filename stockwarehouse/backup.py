from django.conf import settings
import os
from datetime import datetime as dt
import subprocess


# def backup_data():
#     # Chạy lệnh sao lưu cơ sở dữ liệu
#     os.system('python manage.py dbbackup --exclude=portfolio --exclude=stocklist')
    # Đường dẫn đến thư mục lưu trữ sao lưu
    

    # # Access token từ Dropbox App Console
    # access_token = 'sl.Bpdff8ea_TpY-mLi7p2hJjzJGj_Pw4YA1Gx2UJkdQBY7FQVMJH_cBs3w2jPnXPh--q6lSKqyiyAjqShLhTNO3v-ERYUzQbU2gYtkJLKThRjhfPD_8ctIt5weED7a7izNJv7nGC2iu71z'

    # # Khởi tạo Dropbox client
    # dbx = dropbox.Dropbox(access_token)

    # # Tải lên tệp sao lưu lên Dropbox
    # with open(os.path.join(backup_location, backup_file), 'rb') as f:
    #     dbx.files_upload(f.read(), f'/DjangoBackups/{backup_file}')








def run_database_backup():
    """
    Thực hiện sao lưu cơ sở dữ liệu với loại bỏ cơ sở dữ liệu của ứng dụng 'portfolio' và 'stocklist'.
    """
    # Kích hoạt môi trường ảo
    activate_env_command = "source env/bin/activate"
    subprocess.run(activate_env_command, shell=True)

    # Lệnh sao lưu cơ sở dữ liệu
    backup_command = [
        "python",
        "manage.py",
        "dbbackup",
    ]
    
    # Chạy lệnh sao lưu
    subprocess.run(backup_command)
