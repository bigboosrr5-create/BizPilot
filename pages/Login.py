import streamlit as st
import bcrypt
from database import create_connection

st.set_page_config(
    page_title="BizPilot Login",
    page_icon="🔐",
    layout="centered"
)

st.title("🔐 BizPilot Login")
st.caption("Manage • Analyse • Grow")
st.divider()

st.subheader("Business Login")

with st.form("login_form"):
    email = st.text_input("📧 Email Address")
    password = st.text_input("🔑 Password", type="password")

    login = st.form_submit_button("🚀 Login")

if login:

    if email.strip() == "" or password.strip() == "":
        st.error("❌ Please enter Email and Password.")

    else:
        connection = create_connection()

        if connection:
            cursor = connection.cursor(dictionary=True)

            cursor.execute("""
                SELECT
                    business_id,
                    business_name,
                    owner_name,
                    email,
                    password_hash
                FROM businesses
                WHERE email = %s
            """, (email.strip(),))

            business = cursor.fetchone()

            cursor.close()
            connection.close()

            if business:

                stored_hash = business["password_hash"]

                if stored_hash and bcrypt.checkpw(
                    password.encode("utf-8"),
                    stored_hash.encode("utf-8")
                ):

                    st.session_state["logged_in"] = True
                    st.session_state["business_id"] = business["business_id"]
                    st.session_state["business_name"] = business["business_name"]
                    st.session_state["owner_name"] = business["owner_name"]

                    st.success(
                        f"✅ Welcome to BizPilot, {business['business_name']}!"
                    )

                    st.info("Login successful. Dashboard integration is next.")

                else:
                    st.error("❌ Incorrect password.")

            else:
                st.error("❌ Business account not found.")
