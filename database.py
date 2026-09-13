import os
import mysql.connector
import streamlit as st
from dotenv import load_dotenv

# Local development के लिए .env load करें
load_dotenv()


def _get_config(name, default=None):
    """
    पहले Streamlit Cloud Secrets से value लें,
    फिर environment/.env से।
    """
    try:
        value = st.secrets.get(name, None)
        if value not in (None, ""):
            return value
    except Exception:
        pass

    return os.getenv(name, default)


def create_connection():
    try:
        host = _get_config("MYSQL_HOST")
        port = _get_config("MYSQL_PORT", "3307")
        user = _get_config("MYSQL_USER")
        password = _get_config("MYSQL_PASSWORD")
        database = _get_config("MYSQL_DATABASE")

        # Configuration missing होने पर साफ error दें
        missing = []
        if not host:
            missing.append("MYSQL_HOST")
        if not user:
            missing.append("MYSQL_USER")
        if not password:
            missing.append("MYSQL_PASSWORD")
        if not database:
            missing.append("MYSQL_DATABASE")

        if missing:
            st.error(
                "❌ Database configuration missing: "
                + ", ".join(missing)
                + ". Streamlit Cloud में Settings → Secrets में ये values add करें."
            )
            return None

        connection = mysql.connector.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database,
            connection_timeout=15
        )

        if connection.is_connected():
            return connection

        return None

    except ValueError:
        st.error("❌ MYSQL_PORT सही number होना चाहिए.")
        return None

    except mysql.connector.Error as error:
        st.error(f"❌ MySQL connection failed: {error}")
        return None

    except Exception as error:
        st.error(f"❌ Database configuration error: {error}")
        return None
