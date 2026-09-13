import streamlit as st
from database import create_connection
from utils.auth import (
    is_logged_in,
    get_business_id,
    get_business_name
)
from datetime import date

st.set_page_config(
    page_title="BizPilot Sales",
    page_icon="🛒",
    layout="wide"
)

# ==============================
# LOGIN CHECK
# ==============================

if not is_logged_in():
    st.warning("🔐 Please login first to access Sales.")
    st.stop()

business_id = get_business_id()
business_name = get_business_name()

# ==============================
# PAGE HEADER
# ==============================

st.title("🛒 Sales Management")
st.write(f"Manage sales for {business_name}.")
st.divider()

# ==============================
# LOAD PRODUCTS
# ==============================

connection = create_connection()
products = []

if connection:

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            product_id,
            product_name,
            selling_price,
            stock
        FROM products
        WHERE business_id = %s
        AND stock > 0
        ORDER BY product_name
        """,
        (business_id,)
    )

    products = cursor.fetchall()

    cursor.close()
    connection.close()

# ==============================
# LOAD CUSTOMERS
# ==============================

connection = create_connection()
customers = []

if connection:

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            customer_id,
            customer_name
        FROM customers
        WHERE business_id = %s
        ORDER BY customer_name
        """,
        (business_id,)
    )

    customers = cursor.fetchall()

    cursor.close()
    connection.close()

# ==============================
# CHECK DATA
# ==============================

if not products:

    st.warning(
        "⚠️ No products with available stock found. "
        "Please add stock from Products page."
    )

elif not customers:

    st.warning(
        "⚠️ No customers found. "
        "Please add a customer first."
    )

else:

    # ==============================
    # CREATE SALE
    # ==============================

    st.subheader("➕ Create New Sale")

    with st.form("sale_form"):

        customer_options = {
            customer["customer_name"]: customer["customer_id"]
            for customer in customers
        }

        selected_customer = st.selectbox(
            "👤 Select Customer",
            list(customer_options.keys())
        )

        product_options = {
            product["product_name"]: product
            for product in products
        }

        selected_product_name = st.selectbox(
            "📦 Select Product",
            list(product_options.keys())
        )

        selected_product = product_options[
            selected_product_name
        ]

        st.info(
            f"Available Stock: {selected_product['stock']} | "
            f"Selling Price: ₹{selected_product['selling_price']}"
        )

        quantity = st.number_input(
            "🔢 Quantity",
            min_value=1,
            max_value=max(1, selected_product["stock"]),
            value=1,
            step=1
        )

        payment_status = st.selectbox(
            "💳 Payment Status",
            ["Paid", "Pending", "Partial"]
        )

        sale_date = st.date_input(
            "📅 Sale Date",
            value=date.today()
        )

        total_amount = (
            quantity *
            float(selected_product["selling_price"])
        )

        st.metric(
            "💰 Total Amount",
            f"₹{total_amount:,.2f}"
        )

        submit = st.form_submit_button(
            "💾 Save Sale"
        )

    # ==============================
    # SAVE SALE
    # ==============================

    if submit:

        product_id = selected_product["product_id"]
        customer_id = customer_options[selected_customer]

        current_stock = selected_product["stock"]
        selling_price = selected_product["selling_price"]
        if quantity > current_stock:

            st.error(
                "❌ Not enough stock available."
            )

        else:

            connection = create_connection()

            if connection:

                try:

                    cursor = connection.cursor()

                    # ------------------------------
                    # INSERT SALE
                    # ------------------------------

                    sale_query = """
                    INSERT INTO sales
                    (
                        business_id,
                        customer_id,
                        sale_date,
                        total_amount,
                        payment_status
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """

                    sale_values = (
                        business_id,
                        customer_id,
                        sale_date,
                        total_amount,
                        payment_status
                    )

                    cursor.execute(
                        sale_query,
                        sale_values
                    )

                    sale_id = cursor.lastrowid

                    # ------------------------------
                    # INSERT SALE ITEM
                    # ------------------------------

                    subtotal = (
                        quantity *
                        float(selling_price)
                    )

                    item_query = """
                    INSERT INTO sale_items
                    (
                        sale_id,
                        product_id,
                        quantity,
                        selling_price,
                        subtotal
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """

                    item_values = (
                        sale_id,
                        product_id,
                        quantity,
                        selling_price,
                        subtotal
                    )

                    cursor.execute(
                        item_query,
                        item_values
                    )

                    # ------------------------------
                    # UPDATE STOCK
                    # ------------------------------

                    new_stock = (
                        current_stock - quantity
                    )

                    stock_query = """
                    UPDATE products
                    SET stock = %s
                    WHERE product_id = %s
                    AND business_id = %s
                    """

                    cursor.execute(
                        stock_query,
                        (
                            new_stock,
                            product_id,
                            business_id
                        )
                    )

                    # ------------------------------
                    # COMMIT
                    # ------------------------------

                    connection.commit()

                    st.success(
                        f"✅ Sale #{sale_id} saved successfully!"
                    )

                    st.info(
                        f"📦 Remaining Stock: {new_stock}"
                    )

                except Exception as error:

                    connection.rollback()

                    st.error(
                        f"❌ Sale could not be saved: {error}"
                    )

                finally:

                    cursor.close()
                    connection.close()

# ==============================
# SALES HISTORY
# ==============================

st.divider()

st.subheader("📋 Sales History")

connection = create_connection()

if connection:

    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            s.sale_id,
            c.customer_name,
            s.sale_date,
            s.total_amount,
            s.payment_status
        FROM sales s

        LEFT JOIN customers c
            ON s.customer_id = c.customer_id

        WHERE s.business_id = %s

        ORDER BY s.sale_id DESC
        """,
        (business_id,)
    )

    sales = cursor.fetchall()

    cursor.close()
    connection.close()

    if sales:

        st.dataframe(
            sales,
            use_container_width=True
        )

    else:

        st.info(
            "ℹ️ No sales recorded yet."
        )