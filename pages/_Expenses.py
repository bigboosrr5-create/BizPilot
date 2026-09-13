import streamlit as st
from database import create_connection
from utils.auth import (
    is_logged_in,
    get_business_id,
    get_business_name
)
from datetime import date

st.set_page_config(
    page_title="BizPilot Expenses",
    page_icon="💸",
    layout="wide"
)

# ==============================
# LOGIN CHECK
# ==============================

if not is_logged_in():
    st.warning("🔐 Please login first to access Expenses.")
    st.stop()

business_id = get_business_id()
business_name = get_business_name()

# ==============================
# PAGE HEADER
# ==============================

st.title("💸 Expense Management")
st.write(f"Manage expenses for {business_name}.")
st.divider()

# ==============================
# ADD EXPENSE
# ==============================

st.subheader("➕ Add New Expense")

with st.form("expense_form"):

    expense_category = st.selectbox(
        "📂 Expense Category",
        [
            "Rent",
            "Electricity",
            "Transport",
            "Salary",
            "Marketing",
            "Maintenance",
            "Internet",
            "Other"
        ]
    )

    amount = st.number_input(
        "💰 Amount",
        min_value=0.0,
        step=1.0
    )

    expense_date = st.date_input(
        "📅 Expense Date",
        value=date.today()
    )

    description = st.text_area(
        "📝 Description"
    )

    submit = st.form_submit_button(
        "💾 Save Expense"
    )

# ==============================
# SAVE EXPENSE
# ==============================

if submit:

    if amount <= 0:

        st.error(
            "❌ Please enter a valid amount."
        )

    else:

        connection = create_connection()

        if connection:

            try:

                cursor = connection.cursor()

                query = """
                INSERT INTO expenses
                (
                    business_id,
                    expense_category,
                    amount,
                    expense_date,
                    description
                )
                VALUES (%s, %s, %s, %s, %s)
                """

                values = (
                    business_id,
                    expense_category,
                    amount,
                    expense_date,
                    description.strip()
                )

                cursor.execute(
                    query,
                    values
                )

                connection.commit()

                st.success(
                    "✅ Expense added successfully!"
                )

            except Exception as error:

                connection.rollback()

                st.error(
                    f"❌ Expense could not be saved: {error}"
                )

            finally:

                cursor.close()
                connection.close()

# ==============================
# EXPENSE HISTORY
# ==============================

st.divider()

st.subheader("📋 Expense History")

connection = create_connection()

if connection:

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            expense_id,
            expense_category,
            amount,
            expense_date,
            description,
            created_at
        FROM expenses
        WHERE business_id = %s
        ORDER BY expense_id DESC
        """,
        (business_id,)
    )

    expenses = cursor.fetchall()

    cursor.close()
    connection.close()

    if expenses:

        st.dataframe(
            expenses,
            use_container_width=True
        )

    else:

        st.info(
            "ℹ️ No expenses found for this business."
        )