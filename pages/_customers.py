import streamlit as st
from database import create_connection
from utils.auth import is_logged_in, get_business_id, get_business_name

st.set_page_config(
    page_title="BizPilot Customers",
    page_icon="👥",
    layout="wide"
)

# ==============================
# LOGIN CHECK
# ==============================

if not is_logged_in():
    st.warning("🔐 Please login first to access Customers.")
    st.stop()

business_id = get_business_id()
business_name = get_business_name()

# ==============================
# PAGE HEADER
# ==============================

st.title("👥 Customer Management")
st.write(f"Manage customers for {business_name}.")
st.divider()

# ==============================
# ADD CUSTOMER
# ==============================

st.subheader("➕ Add New Customer")

with st.form("customer_form"):

    customer_name = st.text_input("Customer Name")

    col1, col2 = st.columns(2)

    with col1:
        phone = st.text_input("Phone Number")

    with col2:
        email = st.text_input("Email Address")

    address = st.text_area("Address")

    submit = st.form_submit_button(
        "💾 Save Customer"
    )

# ==============================
# SAVE CUSTOMER
# ==============================

if submit:

    if customer_name.strip() == "":
        st.error("❌ Please enter Customer Name.")

    else:

        connection = create_connection()

        if connection:

            try:

                cursor = connection.cursor()

                query = """
                INSERT INTO customers
                (
                    business_id,
                    customer_name,
                    phone,
                    email,
                    address
                )
                VALUES (%s, %s, %s, %s, %s)
                """

                values = (
                    business_id,
                    customer_name.strip(),
                    phone.strip(),
                    email.strip(),
                    address.strip()
                )

                cursor.execute(query, values)

                connection.commit()

                st.success(
                    "✅ Customer added successfully!"
                )

            except Exception as error:

                connection.rollback()

                st.error(
                    f"❌ Customer could not be saved: {error}"
                )

            finally:

                cursor.close()
                connection.close()

# ==============================
# CUSTOMER LIST
# ==============================

st.divider()

st.subheader("📋 Customer List")

connection = create_connection()

if connection:

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            customer_id,
            customer_name,
            phone,
            email,
            address,
            created_at
        FROM customers
        WHERE business_id = %s
        ORDER BY customer_id DESC
        """,
        (business_id,)
    )

    customers = cursor.fetchall()

    cursor.close()
    connection.close()

    if customers:

        st.dataframe(
            customers,
            use_container_width=True
        )

    else:

        st.info(
            "ℹ️ No customers found for this business."
        )