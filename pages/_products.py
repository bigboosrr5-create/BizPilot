import streamlit as st
from database import create_connection
from utils.auth import is_logged_in, get_business_id, get_business_name

st.set_page_config(
    page_title="BizPilot Products",
    page_icon="📦",
    layout="wide"
)

# ==============================
# LOGIN CHECK
# ==============================

if not is_logged_in():
    st.warning("🔐 Please login first to access Products.")
    st.stop()

business_id = get_business_id()
business_name = get_business_name()

# ==============================
# PAGE HEADER
# ==============================

st.title("📦 Product Management")
st.write(f"Manage products for {business_name}.")
st.divider()

# ==============================
# ADD PRODUCT
# ==============================

st.subheader("➕ Add New Product")

with st.form("product_form"):

    product_name = st.text_input("Product Name")

    category = st.text_input("Category")

    col1, col2 = st.columns(2)

    with col1:
        purchase_price = st.number_input(
            "Purchase Price",
            min_value=0.0,
            step=1.0
        )

    with col2:
        selling_price = st.number_input(
            "Selling Price",
            min_value=0.0,
            step=1.0
        )

    col3, col4 = st.columns(2)

    with col3:
        stock = st.number_input(
            "Stock",
            min_value=0,
            step=1
        )

    with col4:
        minimum_stock = st.number_input(
            "Minimum Stock",
            min_value=0,
            step=1
        )

    submit = st.form_submit_button(
        "💾 Save Product"
    )

# ==============================
# SAVE PRODUCT
# ==============================

if submit:

    if product_name.strip() == "":
        st.error("❌ Please enter Product Name.")

    elif selling_price < purchase_price:
        st.warning(
            "⚠️ Selling price is lower than purchase price."
        )

    else:

        connection = create_connection()

        if connection:

            try:

                cursor = connection.cursor()

                query = """
                INSERT INTO products
                (
                    business_id,
                    product_name,
                    category,
                    purchase_price,
                    selling_price,
                    stock,
                    minimum_stock
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """

                values = (
                    business_id,
                    product_name.strip(),
                    category.strip(),
                    purchase_price,
                    selling_price,
                    stock,
                    minimum_stock
                )

                cursor.execute(query, values)

                connection.commit()

                st.success(
                    "✅ Product added successfully!"
                )

            except Exception as error:

                connection.rollback()

                st.error(
                    f"❌ Product could not be saved: {error}"
                )

            finally:

                cursor.close()
                connection.close()

# ==============================
# PRODUCT LIST
# ==============================

st.divider()

st.subheader("📋 Product List")

connection = create_connection()

if connection:

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            product_id,
            product_name,
            category,
            purchase_price,
            selling_price,
            stock,
            minimum_stock,
            created_at
        FROM products
        WHERE business_id = %s
        ORDER BY product_id DESC
        """,
        (business_id,)
    )

    products = cursor.fetchall()

    cursor.close()
    connection.close()

    if products:

        st.dataframe(
            products,
            use_container_width=True
        )

    else:

        st.info(
            "ℹ️ No products found for this business."
        )