import pyodbc
def get_sql_server_connection():
    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=YOUR_SERVER_NAME;'
        'DATABASE=YOUR_DB_NAME;'
        'UID=your_username;'
        'PWD=your_password'
    )
    return conn