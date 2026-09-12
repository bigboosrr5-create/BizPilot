import os
import mysql.connector
from dotenv import load_dotenv

# .env file load करें
load_dotenv()


def create_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT", 3307)),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE")
        )

        if connection.is_connected():
            print("✅ MySQL Database Connected Successfully!")

        return connection

    except mysql.connector.Error as error:
        print("❌ Database Connection Error:", error)
        return None