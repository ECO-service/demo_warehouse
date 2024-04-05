import psycopg2
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus


database_config = [
    #data trade
    {'host': "103.176.22.191",
    'database': "superset",
    'user': "superset",
    'password': "Ecotrading2023",
    'port': "5432"},
    #data giá 
    {'host': "103.176.251.105",
    'database': "ecotrading",
    'user': "admin",
    'password': "Ecotr@ding2023",
    'port': "5432"},
]


def connect(num):
    """ Connect to the PostgreSQL database server """
    database = database_config[num]
    db_connection = None
    try:
        db_connection = psycopg2.connect(
            host= database['host'],
            port=database['port'],
            database =database['database'],
            user=database['user'],
            password=database['password'])

    except (Exception, psycopg2.DatabaseError) as error:
        print(error)

    finally:
        if db_connection is not None:
            #print('Database connect successfully.')
            return db_connection
        else:
            #print("Database connect error")
            exit()

def query_data(num,query):
    db_connection = connect(num)
    cur = db_connection.cursor()
    cur.execute(query)
    try:
        data = cur.fetchall()
        db_connection.commit()
    except psycopg2.ProgrammingError:
        print("No results found.")
        data = []  # Trả về danh sách rỗng nếu không có kết quả
    return data

def execute_query(num,query, data=None):
    db_connection = connect(num)
    cur = db_connection.cursor()
    try:
        if data is None:
            cur.execute(query)
        else:
            cur.execute(query, data)
        db_connection.commit()
        print("Query executed successfully.")
    except Exception as e:
        db_connection.rollback()
        print("Error executing query:", e)
    finally:
        cur.close()
        db_connection.close()


def engine (num):
    database = database_config[num]
    host = database['host']
    port = database['port']
    database_name = database['database']
    user = database['user']
    password = quote_plus(database['password'])
    engine = create_engine(f'postgresql://{user}:{password}@{host}:{port}/{database_name}')
    return engine

def read_sql_to_df(num, query):
    # Kết nối tới cơ sở dữ liệu PostgreSQL
    db_connection = engine (num)
    # Tạo kết nối
    conn = db_connection.connect()
    # Chuyển đối tượng truy vấn sang dạng text
    query_text = text(query)
    # Thực hiện truy vấn để lấy dữ liệu từ cơ sở dữ liệu
    df = pd.read_sql(query_text, conn)
    # Đóng kết nối
    conn.close()
    return df

