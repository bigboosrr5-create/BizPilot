"""
BizPilot — Professional Upload & Analyse
=========================================
Drop-in replacement for: pages/_Upload_Analyse.py

Features
--------
• CSV / Excel / PDF upload
• Multi-sheet Excel handling
• Table extraction from PDFs
• Automatic column detection using exact aliases + fuzzy matching
• Confidence score + mapping review/correction
• Data cleaning and type inference
• Revenue / cost / profit / margin calculations where possible
• Executive KPI dashboard
• Product, category, customer, geography and payment analysis
• Monthly / daily sales trend
• Pareto (80/20) analysis
• Discount, tax, shipping and marketing analysis
• Inventory / low-stock analysis
• Return/refund analysis
• Smart business insights
• Data-quality report
• CSV + Excel + professional PDF export

Important:
This module never invents unavailable business fields. If a metric cannot
be calculated from the uploaded data, it is shown as unavailable.
"""

import io
import os
import re
import tempfile
from difflib import SequenceMatcher
from datetime import datetime

import numpy as np
import pandas as pd
from PIL import Image
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import streamlit as st

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    import fitz  # PyMuPDF — used for scanned/image PDFs
except ImportError:
    fitz = None

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image as RLImage,
)

from utils.auth import is_logged_in, get_business_name, logout


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="BizPilot | Upload & Analyse",
    page_icon="📊",
    layout="wide",
)

LOGO_PATH = os.path.join("assets", "logo.png")


# ============================================================
# PREMIUM UI
# ============================================================

st.markdown(
    """
<style>
.block-container {
    padding-top: 1.4rem;
    padding-bottom: 3rem;
    max-width: 1500px;
}

.main-title {
    font-size: 2.15rem;
    font-weight: 800;
    margin-bottom: 0.15rem;
    letter-spacing: -0.7px;
}

.sub-title {
    color: #64748B;
    font-size: 1rem;
    margin-bottom: 1.25rem;
}

.section-title {
    font-size: 1.35rem;
    font-weight: 750;
    margin-top: 1.2rem;
    margin-bottom: 0.7rem;
}

.insight-card {
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 14px 16px;
    margin: 8px 0;
    background: #FFFFFF;
}

.flow-card {
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 12px;
    text-align: center;
    background: #F8FAFC;
}

.small-muted {
    color: #64748B;
    font-size: 0.86rem;
}

.metric-note {
    color: #64748B;
    font-size: 0.78rem;
}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# LOGIN
# ============================================================

if not is_logged_in():
    st.warning("Please login to access Upload & Analyse.")
    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_container_width=True)

    st.markdown("### Upload & Analyse")
    st.caption(f"Business: {get_business_name() or 'Current Business'}")

    st.divider()

    st.markdown("**Supported files**")
    st.write("CSV • XLSX • XLS • PDF • JPG • PNG • WEBP")

    st.divider()

    if st.button("Logout", use_container_width=True):
        logout()
        st.rerun()


# ============================================================
# HEADER
# ============================================================

st.markdown('<div class="main-title">📊 Upload & Analyse</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Turn an existing business file into a professional analytics dashboard — automatically.</div>',
    unsafe_allow_html=True,
)

flow = st.columns(7)
flow_text = [
    ("1", "Upload"),
    ("2", "Detect"),
    ("3", "Clean"),
    ("4", "Analyse"),
    ("5", "Visualise"),
    ("6", "Insights"),
    ("7", "Report"),
]
for col, (num, label) in zip(flow, flow_text):
    with col:
        st.markdown(
            f'<div class="flow-card"><b>{num}</b><br><span class="small-muted">{label}</span></div>',
            unsafe_allow_html=True,
        )

st.write("")


# ============================================================
# COLUMN SEMANTIC DICTIONARY
# ============================================================

ALIASES = {
    "product_id": [
        "product id", "product_id", "productid", "sku", "sku id",
        "item id", "item code", "product code", "stock keeping unit"
    ],
    "product_name": [
        "product name", "product", "item name", "item", "product title",
        "item description", "product description", "name of product"
    ],
    "category": [
        "category", "product category", "item category", "department",
        "department name", "type", "product type"
    ],
    "subcategory": [
        "subcategory", "sub category", "sub-category", "sub category name"
    ],
    "brand": [
        "brand", "brand name", "manufacturer", "make"
    ],
    "order_id": [
        "order id", "order_id", "order number", "order no", "invoice no",
        "invoice number", "transaction id", "transaction number",
        "bill no", "bill number", "receipt no", "receipt number"
    ],
    "order_date": [
        "order date", "date", "sale date", "sales date", "invoice date",
        "transaction date", "purchase date", "created date", "order_datetime"
    ],
    "quantity": [
        "quantity", "qty", "units", "units sold", "unit sold", "sold quantity",
        "sales quantity", "volume sold", "number sold"
    ],
    "revenue": [
        "revenue", "sales", "sales amount", "total sales", "net sales",
        "gross sales", "turnover", "amount sold", "sale amount",
        "total revenue", "revenue amount", "sales revenue"
    ],
    "unit_price": [
        "selling price", "sale price", "unit price", "selling rate",
        "sales price", "price per unit", "rate", "mrp", "unit selling price"
    ],
    "cost": [
        "cost", "cost price", "purchase price", "buy price", "unit cost",
        "purchase cost", "cost per unit", "buying price"
    ],
    "total_cost": [
        "total cost", "cost amount", "total purchase cost", "cost of goods",
        "cogs", "cost of goods sold", "total cogs"
    ],
    "profit": [
        "profit", "net profit", "gross profit", "profit amount",
        "profit value", "earnings"
    ],
    "profit_margin": [
        "profit margin", "margin", "profit margin %", "profit %",
        "margin percentage", "profit percentage"
    ],
    "discount": [
        "discount", "discount amount", "discount value", "discount %",
        "discount percentage", "rebate"
    ],
    "customer": [
        "customer", "customer name", "client", "client name", "buyer",
        "buyer name", "customer_name"
    ],
    "city": [
        "city", "town", "city name"
    ],
    "state": [
        "state", "state name", "province"
    ],
    "region": [
        "region", "zone", "area", "territory", "location", "market"
    ],
    "payment": [
        "payment", "payment method", "payment mode", "pay mode",
        "payment type", "method of payment"
    ],
    "payment_status": [
        "payment status", "paid status", "payment state", "paid/unpaid",
        "payment_status"
    ],
    "order_status": [
        "order status", "status", "delivery status", "fulfillment status",
        "order state"
    ],
    "return": [
        "return", "returns", "return amount", "refund", "refund amount",
        "returned amount", "return value", "refund value"
    ],
    "stock": [
        "stock", "inventory", "stock quantity", "inventory quantity",
        "available stock", "closing stock", "current stock"
    ],
    "purchase_quantity": [
        "purchase quantity", "purchased quantity", "purchase qty", "buy quantity",
        "received quantity", "received qty", "stock in", "inward quantity",
        "goods received", "units purchased", "purchase units"
    ],
    "opening_stock": [
        "opening stock", "opening inventory", "starting stock", "initial stock",
        "beginning stock", "opening quantity"
    ],
    "minimum_stock": [
        "minimum stock", "min stock", "reorder level", "reorder point",
        "minimum inventory", "safety stock", "threshold stock"
    ],
    "ad_spend": [
        "ad spend", "advertising spend", "marketing spend", "marketing cost",
        "advertising cost", "ads cost", "ad cost", "promotion spend"
    ],
    "shipping": [
        "shipping", "shipping cost", "delivery cost", "freight",
        "logistics cost", "transport cost"
    ],
    "tax": [
        "tax", "tax amount", "gst", "gst amount", "vat", "sales tax",
        "tax value"
    ],
}


LABELS = {
    "product_id": "Product ID / SKU",
    "product_name": "Product",
    "category": "Category",
    "subcategory": "Subcategory",
    "brand": "Brand",
    "order_id": "Order ID",
    "order_date": "Order Date",
    "quantity": "Quantity",
    "revenue": "Revenue / Sales",
    "unit_price": "Selling Price",
    "cost": "Unit Cost",
    "total_cost": "Total Cost",
    "profit": "Profit",
    "profit_margin": "Profit Margin",
    "discount": "Discount",
    "customer": "Customer",
    "city": "City",
    "state": "State",
    "region": "Region",
    "payment": "Payment Method",
    "payment_status": "Payment Status",
    "order_status": "Order Status",
    "return": "Return / Refund",
    "stock": "Stock / Inventory",
    "minimum_stock": "Minimum / Reorder Stock",
    "purchase_quantity": "Purchase Quantity",
    "opening_stock": "Opening Stock",
    "ad_spend": "Marketing / Ad Spend",
    "shipping": "Shipping Cost",
    "tax": "Tax / GST",
}


NUMERIC_FIELDS = {
    "quantity", "revenue", "unit_price", "cost", "total_cost",
    "profit", "profit_margin", "discount", "return", "stock",
    "minimum_stock", "purchase_quantity", "opening_stock", "ad_spend", "shipping", "tax"
}


# ============================================================
# HELPERS
# ============================================================

def normalize_text(value):
    value = str(value).strip().lower()
    value = re.sub(r"[%₹$€£]", "", value)
    value = re.sub(r"[_\-/]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def clean_dataframe(df):
    df = df.copy()

    df.columns = [
        str(c).replace("\n", " ").replace("\r", " ").strip()
        for c in df.columns
    ]

    # Remove unnamed Excel/PDF columns
    valid_cols = [
        c for c in df.columns
        if not str(c).lower().startswith("unnamed")
    ]
    df = df[valid_cols]

    df = df.dropna(axis=0, how="all")
    df = df.dropna(axis=1, how="all")

    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].map(
                lambda x: x.strip() if isinstance(x, str) else x
            )

    df = df.drop_duplicates().reset_index(drop=True)
    return df


def numeric_clean(series):
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    s = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("€", "", regex=False)
        .str.replace("£", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(s, errors="coerce")


def date_score(series):
    parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
    valid = parsed.notna().mean()
    return float(valid)


def semantic_score(column, aliases):
    col = normalize_text(column)

    best = 0.0
    best_alias = ""

    for alias in aliases:
        a = normalize_text(alias)

        if col == a:
            score = 1.00
        elif a in col or col in a:
            score = 0.84
        else:
            score = SequenceMatcher(None, col, a).ratio()

        if score > best:
            best = score
            best_alias = alias

    return best, best_alias


def detect_columns(df):
    candidates = {}

    for field, aliases in ALIASES.items():
        options = []

        for col in df.columns:
            score, matched_alias = semantic_score(col, aliases)

            # Additional date intelligence
            if field == "order_date":
                try:
                    dscore = date_score(df[col])
                    score = max(score, min(0.98, dscore * 0.98))
                except Exception:
                    pass

            # Numeric intelligence
            if field in NUMERIC_FIELDS:
                numeric_ratio = numeric_clean(df[col]).notna().mean()
                if numeric_ratio >= 0.70:
                    score = min(1.0, score + 0.04)

            options.append((col, score, matched_alias))

        options.sort(key=lambda x: x[1], reverse=True)
        candidates[field] = options

    mapping = {}
    confidence = {}
    used = set()

    # First pass: strongest exact-ish semantic matches
    for field in sorted(candidates, key=lambda f: candidates[f][0][1], reverse=True):
        for col, score, _alias in candidates[field]:
            if score >= 0.92 and col not in used:
                mapping[field] = col
                confidence[field] = score
                used.add(col)
                break

    # Second pass: good fuzzy matches, with stricter threshold
    for field in candidates:
        if field in mapping:
            continue

        for col, score, _alias in candidates[field]:
            if col in used:
                continue

            threshold = 0.78

            # Avoid dangerous automatic assumptions
            if field in {"revenue", "cost", "profit", "unit_price", "total_cost"}:
                threshold = 0.84

            if score >= threshold:
                mapping[field] = col
                confidence[field] = score
                used.add(col)
                break

    return mapping, confidence, candidates


def apply_mapping(df, mapping):
    work = df.copy()

    for field, source_col in mapping.items():
        if source_col and source_col in work.columns:
            work[f"__{field}"] = work[source_col]

    # Numeric conversion
    for field in NUMERIC_FIELDS:
        c = f"__{field}"
        if c in work.columns:
            work[c] = numeric_clean(work[c])

    # Date conversion
    if "__order_date" in work.columns:
        work["__order_date"] = pd.to_datetime(
            work["__order_date"], errors="coerce", dayfirst=True
        )

    return work


def safe_sum(df, field):
    col = f"__{field}"
    if col not in df.columns:
        return None
    value = pd.to_numeric(df[col], errors="coerce").sum(min_count=1)
    return None if pd.isna(value) else float(value)


def safe_mean(df, field):
    col = f"__{field}"
    if col not in df.columns:
        return None
    value = pd.to_numeric(df[col], errors="coerce").mean()
    return None if pd.isna(value) else float(value)


def money(value):
    if value is None or pd.isna(value):
        return "N/A"
    return f"₹{value:,.2f}"


def number(value):
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:,.0f}"


def pct(value):
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.2f}%"


def metric_available(work, field):
    return f"__{field}" in work.columns and work[f"__{field}"].notna().any()


def make_derived_metrics(work):
    """Create trustworthy financial and inventory metrics from raw data.

    Rules:
    - Revenue is an explicit sales/revenue amount when supplied; otherwise Qty × Selling Price.
    - Total cost is an explicit total/COGS amount when supplied; otherwise Qty × Unit Cost.
    - Profit is ALWAYS recomputed from Revenue - Total Cost when both are available.
      A supplied profit column is used only when cost is unavailable.
    - Margin is ALWAYS recomputed as Profit / Revenue × 100 when possible.
    - Stock is calculated at product level as Opening + Purchases - Units Sold,
      using the latest opening/stock value per product so repeated transaction rows
      do not inflate inventory.
    - No unavailable value is invented.
    """
    work = work.copy()

    for field in NUMERIC_FIELDS | {"purchase_quantity", "opening_stock"}:
        col = f"__{field}"
        if col in work.columns:
            work[col] = numeric_clean(work[col])

    def has(field):
        return metric_available(work, field)

    def num(field):
        return pd.to_numeric(work[f"__{field}"], errors="coerce")

    # ------------------------- REVENUE -------------------------
    # Prefer an explicit revenue/sales amount. Only derive when it is absent.
    if not has("revenue") and has("quantity") and has("unit_price"):
        work["__revenue"] = num("quantity") * num("unit_price")

    # ------------------------- TOTAL COST ----------------------
    # A mapped 'total_cost' means the source already provides a row total.
    # Never multiply an explicit Total Cost by quantity.
    if not has("total_cost") and has("cost") and has("quantity"):
        work["__total_cost"] = num("cost") * num("quantity")
    elif not has("total_cost") and has("cost"):
        work["__total_cost"] = num("cost")

    # ------------------------- PROFIT --------------------------
    # Never trust a supplied profit when reliable Revenue and Total Cost exist.
    # This prevents contradictory KPI cards.
    if has("revenue") and has("total_cost"):
        work["__profit"] = num("revenue") - num("total_cost")
    elif not has("profit"):
        work["__profit"] = np.nan

    # ------------------------- MARGIN --------------------------
    if has("revenue") and has("profit"):
        rev = num("revenue")
        prof = num("profit")
        work["__profit_margin"] = np.where(
            rev.ne(0), (prof / rev) * 100, np.nan
        )

    # ------------------------- OPERATING PROFIT ----------------
    if has("revenue") and has("total_cost"):
        extra = pd.Series(0.0, index=work.index)
        found = False
        for field in ("shipping", "tax", "ad_spend"):
            if has(field):
                extra = extra.add(num(field).fillna(0), fill_value=0)
                found = True
        if found:
            work["__operating_profit"] = num("revenue") - num("total_cost") - extra

    # ------------------------- INVENTORY -----------------------
    # Existing current/closing stock wins. Otherwise calculate product-level
    # closing stock from opening + purchases - sold, avoiding repeated openings.
    if not has("stock") and has("opening_stock") and has("quantity"):
        if "__product_name" in work.columns:
            keys = work["__product_name"].astype(str).str.strip()
            base = work.copy()
            base["__product_key"] = keys
            base["__sold_for_stock"] = num("quantity").fillna(0)
            if has("purchase_quantity"):
                base["__purchase_for_stock"] = num("purchase_quantity").fillna(0)
            else:
                base["__purchase_for_stock"] = 0.0

            if "__order_date" in base.columns:
                base = base.sort_values("__order_date")

            opening_map = base.groupby("__product_key")["__opening_stock"].last()
            purchase_map = base.groupby("__product_key")["__purchase_for_stock"].sum()
            sold_map = base.groupby("__product_key")["__sold_for_stock"].sum()

            stock_map = (
                opening_map.fillna(0)
                + purchase_map.reindex(opening_map.index).fillna(0)
                - sold_map.reindex(opening_map.index).fillna(0)
            ).clip(lower=0)

            work["__stock"] = keys.map(stock_map)
        else:
            # Without a product key, only a single-row opening/purchase series
            # can be safely used. Repeated transaction rows are not summed here.
            if len(work) == 1:
                work["__stock"] = (
                    num("opening_stock").fillna(0)
                    + (num("purchase_quantity").fillna(0) if has("purchase_quantity") else 0)
                    - num("quantity").fillna(0)
                ).clip(lower=0)

    return work


def read_csv(file):
    raw = file.getvalue()
    for encoding in ["utf-8-sig", "utf-8", "cp1252", "latin1"]:
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=encoding)
        except Exception:
            continue
    raise ValueError("CSV could not be decoded.")


def read_excel(file):
    sheets = pd.read_excel(file, sheet_name=None)
    cleaned = {}

    for name, frame in sheets.items():
        frame = clean_dataframe(frame)
        if not frame.empty:
            cleaned[name] = frame

    if not cleaned:
        raise ValueError("No usable Excel sheet was found.")

    # Choose largest sheet as primary.
    primary_name = max(
        cleaned,
        key=lambda name: cleaned[name].shape[0] * cleaned[name].shape[1]
    )

    return cleaned[primary_name], cleaned


def _ocr_available():
    return pytesseract is not None


def _ocr_image_to_dataframe(image):
    """Convert an image of a business table into a best-effort DataFrame.

    The OCR result is grouped by visual text lines and column positions. The
    first useful line is treated as a header; later lines become records.
    This keeps the workflow automatic while still allowing the normal column
    detector to rename/map business fields afterwards.
    """
    if pytesseract is None:
        raise ImportError(
            "Image/PDF OCR requires pytesseract and a local Tesseract OCR installation."
        )

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    # A little upscaling improves OCR for screenshots/scanned tables.
    scale = 1.6 if max(image.size) < 2200 else 1.0
    if scale != 1.0:
        image = image.resize(
            (int(image.width * scale), int(image.height * scale))
        )

    data = pytesseract.image_to_data(
        image,
        output_type=pytesseract.Output.DICT,
        config="--psm 6",
    )

    words = []
    for i, text in enumerate(data.get("text", [])):
        text = str(text).strip()
        try:
            conf = float(data["conf"][i])
        except Exception:
            conf = -1
        if not text or conf < 15:
            continue
        words.append({
            "text": text,
            "left": int(data["left"][i]),
            "top": int(data["top"][i]),
            "width": int(data["width"][i]),
            "height": int(data["height"][i]),
            "line": (int(data["block_num"][i]), int(data["par_num"][i]), int(data["line_num"][i])),
        })

    if not words:
        raise ValueError("No readable text was found in the image.")

    # Group OCR words into visual lines.
    lines = {}
    for w in words:
        lines.setdefault(w["line"], []).append(w)

    line_rows = []
    for _, items in sorted(lines.items(), key=lambda kv: (min(x["top"] for x in kv[1]), min(x["left"] for x in kv[1]))):
        items = sorted(items, key=lambda x: x["left"])
        line_rows.append(items)

    # Ignore obvious title/metadata lines above a tabular header. A likely
    # header contains at least two known business concepts.
    header_idx = 0
    best_score = -1
    known_terms = set()
    for aliases in ALIASES.values():
        known_terms.update(normalize_text(a) for a in aliases)

    for idx, items in enumerate(line_rows[:12]):
        text_line = " ".join(x["text"] for x in items)
        norm = normalize_text(text_line)
        score = sum(1 for term in known_terms if term in norm)
        score += min(len(items), 8) * 0.05
        if score > best_score:
            best_score = score
            header_idx = idx

    header_items = line_rows[header_idx]
    headers = [x["text"] for x in header_items]
    headers = _unique_headers(headers)

    if len(headers) < 2:
        # Fall back to text rows; this still lets manual mapping repair a
        # poorly recognised image.
        text_rows = [[x["text"] for x in row] for row in line_rows]
        max_cols = max(len(r) for r in text_rows)
        headers = [f"Column {i+1}" for i in range(max_cols)]
        body = [r + [""] * (max_cols - len(r)) for r in text_rows]
        return pd.DataFrame(body, columns=headers)

    # Preserve header x positions before making names unique.
    header_positions = [x["left"] for x in header_items]
    rows = []
    for items in line_rows[header_idx + 1:]:
        if not items:
            continue
        cells = [""] * len(header_positions)
        for item in items:
            idx = min(range(len(header_positions)), key=lambda j: abs(item["left"] - header_positions[j]))
            cells[idx] = (cells[idx] + " " + item["text"]).strip()
        if any(cells):
            rows.append(cells)

    if not rows:
        raise ValueError("OCR found a header but no usable table rows.")

    return pd.DataFrame(rows, columns=headers)


def _unique_headers(headers):
    seen = {}
    out = []
    for i, h in enumerate(headers, start=1):
        h = re.sub(r"\s+", " ", str(h).strip()) or f"Column {i}"
        count = seen.get(h.lower(), 0)
        seen[h.lower()] = count + 1
        out.append(h if count == 0 else f"{h}_{count+1}")
    return out


def _extract_scanned_pdf(file):
    if fitz is None or pytesseract is None:
        raise ImportError(
            "Scanned/image PDF support requires PyMuPDF (fitz) + pytesseract + Tesseract OCR."
        )

    raw = file.getvalue()
    document = fitz.open(stream=raw, filetype="pdf")
    frames = []

    for page_no, page in enumerate(document, start=1):
        pix = page.get_pixmap(matrix=fitz.Matrix(1.7, 1.7), alpha=False)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        try:
            frame = _ocr_image_to_dataframe(image)
            if not frame.empty:
                frame["__pdf_page"] = page_no
                frames.append(frame)
        except Exception:
            continue

    if not frames:
        raise ValueError("OCR could not find a usable table in the scanned PDF.")

    # OCR pages may produce slightly different headers. Keep the union and
    # allow the normal detector to map equivalent fields.
    return clean_dataframe(pd.concat(frames, ignore_index=True, sort=False))


def extract_image(file):
    if pytesseract is None:
        raise ImportError(
            "Image OCR requires pytesseract and a local Tesseract OCR installation."
        )
    image = Image.open(io.BytesIO(file.getvalue()))
    return clean_dataframe(_ocr_image_to_dataframe(image))


def extract_pdf(file):
    """Extract normal PDF tables first; fall back to OCR for scanned PDFs."""
    if pdfplumber is None:
        # Directly try OCR when the table extractor is not installed.
        return _extract_scanned_pdf(file)

    frames = []
    raw = file.getvalue()

    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue
                header = table[0]
                body = table[1:]
                if not header:
                    continue
                header = [
                    str(x).strip() if x is not None else f"Column {i+1}"
                    for i, x in enumerate(header)
                ]
                header = _unique_headers(header)
                frame = pd.DataFrame(body, columns=header)
                frame["__pdf_page"] = page_no
                frames.append(frame)

    if frames:
        return clean_dataframe(pd.concat(frames, ignore_index=True, sort=False))

    # No vector/text table found: treat it as a scanned/image PDF.
    return _extract_scanned_pdf(file)


def format_table(df, max_rows=20):
    out = df.head(max_rows).copy()

    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")

    return out


def group_metric(work, group_field, metric="revenue", top_n=15):
    gcol = f"__{group_field}"
    mcol = f"__{metric}"

    if gcol not in work.columns or mcol not in work.columns:
        return None

    temp = work[[gcol, mcol]].copy()
    temp[gcol] = temp[gcol].astype(str).str.strip()
    temp[mcol] = pd.to_numeric(temp[mcol], errors="coerce")
    temp = temp.dropna(subset=[gcol, mcol])

    if temp.empty:
        return None

    result = (
        temp.groupby(gcol, as_index=False)[mcol]
        .sum()
        .sort_values(mcol, ascending=False)
        .head(top_n)
    )
    result.columns = [LABELS.get(group_field, group_field), metric.title()]
    return result


def create_bar(df, x, y, title, horizontal=False):
    if df is None or df.empty:
        return None

    if horizontal:
        fig = px.bar(
            df,
            x=y,
            y=x,
            orientation="h",
            title=title,
            text_auto=".2s",
        )
    else:
        fig = px.bar(
            df,
            x=x,
            y=y,
            title=title,
            text_auto=".2s",
        )

    fig.update_layout(
        height=430,
        margin=dict(l=20, r=20, t=60, b=20),
        hovermode="x unified",
    )
    return fig


def create_pie(df, names, values, title):
    if df is None or df.empty:
        return None

    fig = px.pie(
        df,
        names=names,
        values=values,
        title=title,
        hole=0.42,
    )
    fig.update_layout(
        height=430,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return fig


def _register_report_fonts():
    """Register a Unicode font so ₹ and other symbols render correctly in PDFs."""
    try:
        from matplotlib import font_manager
        regular = font_manager.findfont("DejaVu Sans", fallback_to_default=True)
        bold = font_manager.findfont("DejaVu Sans:style=bold", fallback_to_default=True)
        if "BizDejaVu" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("BizDejaVu", regular))
        if "BizDejaVuBold" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("BizDejaVuBold", bold))
        return "BizDejaVu", "BizDejaVuBold"
    except Exception:
        return "Helvetica", "Helvetica-Bold"


REPORT_FONT, REPORT_BOLD = _register_report_fonts()


def add_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(REPORT_FONT, 8)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawCentredString(
        A4[0] / 2,
        7 * mm,
        f"BizPilot • Generated {datetime.now().strftime('%d %b %Y, %I:%M %p')}  •  Page {doc.page}"
    )
    canvas.restoreState()


# ============================================================
# UPLOAD
# ============================================================

uploaded = st.file_uploader(
    "Upload your existing business file",
    type=["csv", "xlsx", "xls", "pdf", "png", "jpg", "jpeg", "webp"],
    help="Upload the actual file you already have. No manual data formatting is required.",
)

if uploaded is None:
    st.info(
        "Upload CSV/Excel, a table PDF, a scanned PDF, or a clear JPG/PNG/WEBP table image. BizPilot will read the file, create columns, clean the data and analyse it automatically."
    )
    st.stop()

if extension := uploaded.name.lower().split(".")[-1] if uploaded else None:
    if extension in {"pdf", "png", "jpg", "jpeg", "webp"}:
        st.caption("OCR mode: best results come from a clear, straight, high-resolution table image/PDF with visible column headings.")


# ============================================================
# READ FILE
# ============================================================

try:
    extension = uploaded.name.lower().split(".")[-1]

    if extension == "csv":
        raw_df = read_csv(uploaded)
        sheets = None

    elif extension in {"xlsx", "xls"}:
        raw_df, sheets = read_excel(uploaded)

    elif extension == "pdf":
        raw_df = extract_pdf(uploaded)
        sheets = None

    elif extension in {"png", "jpg", "jpeg", "webp"}:
        raw_df = extract_image(uploaded)
        sheets = None

    else:
        st.error("Unsupported file type.")
        st.stop()

    raw_df = clean_dataframe(raw_df)

except Exception as e:
    st.error(f"Could not read the file: {e}")
    st.stop()


if raw_df.empty:
    st.error("The uploaded file contains no usable rows.")
    st.stop()


# ============================================================
# DETECTION
# ============================================================

mapping, confidence, candidates = detect_columns(raw_df)

with st.spinner("Understanding columns and preparing analytics..."):
    work = apply_mapping(raw_df, mapping)
    work = make_derived_metrics(work)


# ============================================================
# MAPPING REVIEW
# ============================================================

st.markdown('<div class="section-title">🧠 Automatic Column Understanding</div>', unsafe_allow_html=True)

det_rows = []
for field, source in mapping.items():
    det_rows.append(
        {
            "BizPilot Field": LABELS.get(field, field),
            "Detected Column": source,
            "Confidence": f"{confidence.get(field, 0)*100:.0f}%",
        }
    )

if det_rows:
    st.dataframe(
        pd.DataFrame(det_rows),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.warning(
        "No standard business fields were confidently detected. "
        "You can map important columns manually below."
    )

with st.expander("⚙️ Review / Correct Column Mapping"):
    st.caption(
        "This changes only how BizPilot analyses the uploaded data. "
        "Your original file is not modified."
    )

    corrected = dict(mapping)

    fields_for_mapping = [
        "product_name", "category", "brand", "order_id", "order_date",
        "quantity", "purchase_quantity", "opening_stock", "revenue", "unit_price", "cost", "total_cost", "profit",
        "profit_margin", "discount", "customer", "city", "state", "region",
        "payment", "payment_status", "order_status", "return", "stock",
        "minimum_stock", "ad_spend", "shipping", "tax",
    ]

    cols = ["— Not detected —"] + list(raw_df.columns)

    map_columns = st.columns(3)

    for i, field in enumerate(fields_for_mapping):
        with map_columns[i % 3]:
            current = corrected.get(field)
            default_index = cols.index(current) if current in cols else 0

            selected = st.selectbox(
                LABELS[field],
                cols,
                index=default_index,
                key=f"mapping_{field}",
            )

            corrected[field] = None if selected == "— Not detected —" else selected

    if st.button("Apply Mapping & Recalculate", type="primary"):
        mapping = corrected
        work = apply_mapping(raw_df, mapping)
        work = make_derived_metrics(work)
        st.success("Mapping applied.")
        st.rerun()


# ============================================================
# DATA OVERVIEW
# ============================================================

st.markdown('<div class="section-title">📁 Data Overview</div>', unsafe_allow_html=True)

overview_cols = st.columns(5)
overview_cols[0].metric("Rows", f"{len(raw_df):,}")
overview_cols[1].metric("Columns", f"{len(raw_df.columns):,}")
overview_cols[2].metric("Detected Fields", f"{len(mapping):,}")
overview_cols[3].metric(
    "Cleaned Rows",
    f"{len(work):,}"
)
overview_cols[4].metric(
    "Data Completeness",
    f"{(1 - raw_df.isna().mean().mean()) * 100:.1f}%"
)

with st.expander("👀 View Cleaned Data Preview"):
    st.dataframe(
        format_table(raw_df, 30),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# KPI CALCULATION
# ============================================================

revenue = safe_sum(work, "revenue")
cost = safe_sum(work, "total_cost")
profit = safe_sum(work, "profit")
units = safe_sum(work, "quantity")
discount = safe_sum(work, "discount")
returns = safe_sum(work, "return")
ad_spend = safe_sum(work, "ad_spend")
shipping = safe_sum(work, "shipping")
tax = safe_sum(work, "tax")

margin = None
if revenue not in (None, 0) and profit is not None:
    margin = profit / revenue * 100

orders = None
if "__order_id" in work.columns:
    orders = work["__order_id"].nunique(dropna=True)

customers = None
if "__customer" in work.columns:
    customers = work["__customer"].nunique(dropna=True)

avg_order = None
if revenue is not None and orders:
    avg_order = revenue / orders

roas = None
if revenue is not None and ad_spend not in (None, 0):
    roas = revenue / ad_spend


# ============================================================
# EXECUTIVE DASHBOARD
# ============================================================

st.markdown('<div class="section-title">📌 Executive Business Dashboard</div>', unsafe_allow_html=True)

k1, k2, k3, k4, k5, k6 = st.columns(6)

k1.metric("Revenue / Sales", money(revenue))
k2.metric("Total Cost", money(cost))
k3.metric("Profit", money(profit))
k4.metric("Profit Margin", pct(margin))
k5.metric("Orders", number(orders))
k6.metric("Units Sold", number(units))

k7, k8, k9, k10, k11, k12 = st.columns(6)

k7.metric("Customers", number(customers))
k8.metric("Avg. Order Value", money(avg_order))
k9.metric("Discount", money(discount))
k10.metric("Returns / Refunds", money(returns))
k11.metric("Ad Spend", money(ad_spend))
k12.metric("ROAS", f"{roas:.2f}x" if roas is not None else "N/A")


# ============================================================
# DATE FILTER
# ============================================================

filtered = work.copy()

if "__order_date" in work.columns and work["__order_date"].notna().any():
    min_date = work["__order_date"].min().date()
    max_date = work["__order_date"].max().date()

    st.markdown('<div class="section-title">🗓️ Analysis Period</div>', unsafe_allow_html=True)

    d1, d2 = st.columns(2)
    start = d1.date_input("From", min_date, key="analysis_start")
    end = d2.date_input("To", max_date, key="analysis_end")

    if start > end:
        st.error("Start date cannot be after end date.")
        st.stop()

    filtered = work[
        (work["__order_date"].dt.date >= start)
        & (work["__order_date"].dt.date <= end)
    ].copy()

    if filtered.empty:
        st.warning("No records exist in the selected date range.")
        st.stop()


# ============================================================
# PRODUCT PERFORMANCE
# ============================================================

if "__product_name" in filtered.columns:
    st.markdown('<div class="section-title">🏆 Product Performance</div>', unsafe_allow_html=True)

    product_rev = group_metric(filtered, "product_name", "revenue", 20)
    product_profit = group_metric(filtered, "product_name", "profit", 20)
    product_qty = group_metric(filtered, "product_name", "quantity", 20)

    p1, p2 = st.columns(2)

    with p1:
        fig = create_bar(
            product_rev,
            "Product",
            "Revenue",
            "Top Products by Revenue",
            horizontal=True,
        )
        if fig:
            st.plotly_chart(fig, use_container_width=True)

    with p2:
        if product_profit is not None:
            fig = create_bar(
                product_profit,
                "Product",
                "Profit",
                "Top Products by Profit",
                horizontal=True,
            )
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Profit analysis requires revenue + cost/profit data.")

    p3, p4 = st.columns(2)

    with p3:
        if product_rev is not None:
            st.plotly_chart(
                create_pie(
                    product_rev,
                    "Product",
                    "Revenue",
                    "Revenue Share by Product",
                ),
                use_container_width=True,
            )

    with p4:
        if product_qty is not None:
            st.plotly_chart(
                create_bar(
                    product_qty,
                    "Product",
                    "Quantity",
                    "Units Sold by Product",
                    horizontal=True,
                ),
                use_container_width=True,
            )

    if product_rev is not None:
        st.dataframe(
            product_rev,
            use_container_width=True,
            hide_index=True,
        )

        # Pareto / 80-20
        pareto = product_rev.copy()
        pareto["Cumulative %"] = (
            pareto["Revenue"].cumsum()
            / pareto["Revenue"].sum()
            * 100
        )

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=pareto["Product"],
                y=pareto["Revenue"],
                name="Revenue",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=pareto["Product"],
                y=pareto["Cumulative %"],
                name="Cumulative %",
                yaxis="y2",
                mode="lines+markers",
            )
        )
        fig.update_layout(
            title="Product Revenue Pareto Analysis",
            yaxis=dict(title="Revenue"),
            yaxis2=dict(
                title="Cumulative %",
                overlaying="y",
                side="right",
                range=[0, 105],
            ),
            height=470,
            margin=dict(l=20, r=20, t=60, b=80),
        )
        st.plotly_chart(fig, use_container_width=True)


# ============================================================
# CATEGORY ANALYSIS
# ============================================================

if "__category" in filtered.columns:
    st.markdown('<div class="section-title">📦 Category Intelligence</div>', unsafe_allow_html=True)

    cat_rev = group_metric(filtered, "category", "revenue", 20)
    cat_profit = group_metric(filtered, "category", "profit", 20)

    c1, c2 = st.columns(2)

    with c1:
        if cat_rev is not None:
            st.plotly_chart(
                create_bar(
                    cat_rev,
                    "Category",
                    "Revenue",
                    "Revenue by Category",
                ),
                use_container_width=True,
            )

    with c2:
        if cat_rev is not None:
            st.plotly_chart(
                create_pie(
                    cat_rev,
                    "Category",
                    "Revenue",
                    "Category Revenue Mix",
                ),
                use_container_width=True,
            )

    if cat_profit is not None:
        st.dataframe(
            cat_profit,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# SALES TREND
# ============================================================

if "__order_date" in filtered.columns and metric_available(filtered, "revenue"):
    st.markdown('<div class="section-title">📈 Sales Trend & Growth</div>', unsafe_allow_html=True)

    trend = filtered.dropna(subset=["__order_date", "__revenue"]).copy()

    if not trend.empty:
        trend["Date"] = trend["__order_date"].dt.date
        daily = trend.groupby("Date", as_index=False)["__revenue"].sum()
        daily.columns = ["Date", "Revenue"]

        fig = px.line(
            daily,
            x="Date",
            y="Revenue",
            markers=True,
            title="Revenue Trend Over Time",
        )
        fig.update_layout(
            height=440,
            margin=dict(l=20, r=20, t=60, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

        monthly = trend.assign(
            Month=trend["__order_date"].dt.to_period("M").astype(str)
        ).groupby("Month", as_index=False)["__revenue"].sum()
        monthly.columns = ["Month", "Revenue"]

        if len(monthly) >= 2:
            monthly["Growth %"] = monthly["Revenue"].pct_change() * 100

            st.dataframe(
                monthly,
                use_container_width=True,
                hide_index=True,
            )


# ============================================================
# CUSTOMER ANALYSIS
# ============================================================

if "__customer" in filtered.columns and metric_available(filtered, "revenue"):
    st.markdown('<div class="section-title">👥 Customer Intelligence</div>', unsafe_allow_html=True)

    cust = group_metric(filtered, "customer", "revenue", 20)

    if cust is not None:
        c1, c2 = st.columns(2)

        with c1:
            st.plotly_chart(
                create_bar(
                    cust,
                    "Customer",
                    "Revenue",
                    "Top Customers by Revenue",
                    horizontal=True,
                ),
                use_container_width=True,
            )

        with c2:
            st.dataframe(cust, use_container_width=True, hide_index=True)

        total_cust_revenue = cust["Revenue"].sum()
        top_customer_share = (
            cust.iloc[0]["Revenue"] / total_cust_revenue * 100
            if total_cust_revenue else None
        )


# ============================================================
# GEOGRAPHY
# ============================================================

geo_field = None
for f in ["city", "state", "region"]:
    if f"__{f}" in filtered.columns:
        geo_field = f
        break

if geo_field and metric_available(filtered, "revenue"):
    st.markdown('<div class="section-title">🌍 Geographic Performance</div>', unsafe_allow_html=True)

    geo = group_metric(filtered, geo_field, "revenue", 20)

    if geo is not None:
        st.plotly_chart(
            create_bar(
                geo,
                LABELS[geo_field],
                "Revenue",
                f"Revenue by {LABELS[geo_field]}",
                horizontal=True,
            ),
            use_container_width=True,
        )
        st.dataframe(geo, use_container_width=True, hide_index=True)


# ============================================================
# PAYMENT / ORDER STATUS
# ============================================================

pay_field = "payment"
status_field = "order_status"

if f"__{pay_field}" in filtered.columns:
    st.markdown('<div class="section-title">💳 Payment & Order Status</div>', unsafe_allow_html=True)

    p1, p2 = st.columns(2)

    with p1:
        payment_counts = (
            filtered["__payment"]
            .astype(str)
            .value_counts()
            .reset_index()
        )
        payment_counts.columns = ["Payment Method", "Orders"]
        st.plotly_chart(
            create_pie(payment_counts, "Payment Method", "Orders", "Payment Method Mix"),
            use_container_width=True,
        )

    with p2:
        if f"__{status_field}" in filtered.columns:
            status_counts = (
                filtered["__order_status"]
                .astype(str)
                .value_counts()
                .reset_index()
            )
            status_counts.columns = ["Order Status", "Orders"]
            st.plotly_chart(
                create_pie(
                    status_counts,
                    "Order Status",
                    "Orders",
                    "Order Status Distribution",
                ),
                use_container_width=True,
            )


# ============================================================
# INVENTORY INTELLIGENCE
# ============================================================

if "__stock" in filtered.columns:
    st.markdown('<div class="section-title">📦 Inventory Intelligence</div>', unsafe_allow_html=True)

    inv_cols = ["__stock"]
    if "__product_name" in filtered.columns:
        inv_cols.insert(0, "__product_name")
    if "__minimum_stock" in filtered.columns:
        inv_cols.append("__minimum_stock")

    inv = filtered[inv_cols].copy()

    rename = {
        "__product_name": "Product",
        "__stock": "Stock",
        "__minimum_stock": "Minimum Stock",
    }
    inv = inv.rename(columns=rename)

    if "Minimum Stock" in inv.columns:
        inv["Stock Status"] = np.where(
            inv["Stock"] <= inv["Minimum Stock"],
            "Low Stock",
            "Healthy",
        )

        low_count = (inv["Stock Status"] == "Low Stock").sum()
        st.metric("Low Stock Items", int(low_count))

        if low_count:
            st.warning(
                f"{low_count} item(s) are at or below their minimum/reorder stock level."
            )

    st.dataframe(
        inv.drop_duplicates(),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# DISCOUNT / MARKETING / COST INTELLIGENCE
# ============================================================

st.markdown('<div class="section-title">💰 Commercial Intelligence</div>', unsafe_allow_html=True)

commercial = st.columns(4)

commercial[0].metric("Discount", money(discount))
commercial[1].metric("Shipping", money(shipping))
commercial[2].metric("Tax / GST", money(tax))
commercial[3].metric("Marketing Spend", money(ad_spend))

if ad_spend not in (None, 0) and revenue is not None:
    st.info(
        f"Estimated ROAS: **{roas:.2f}x** — based on available revenue and marketing/ad spend."
    )

if discount is not None and revenue is not None:
    discount_ratio = discount / revenue * 100 if revenue else None
    if discount_ratio is not None:
        st.write(
            f"Discount-to-revenue ratio: **{discount_ratio:.2f}%**"
        )


# ============================================================
# SMART INSIGHTS
# ============================================================

st.markdown('<div class="section-title">🧠 Smart Business Insights</div>', unsafe_allow_html=True)

insights = []

if revenue is not None:
    insights.append(f"Total analysed revenue/sales are **{money(revenue)}**.")

if profit is not None:
    if profit > 0:
        insights.append(f"Overall analysed profit is **{money(profit)}**.")
    elif profit < 0:
        insights.append(f"The analysed dataset shows an overall loss of **{money(abs(profit))}**.")
    else:
        insights.append("The analysed dataset is approximately at break-even.")

if margin is not None:
    if margin >= 30:
        insights.append(
            f"Overall profit margin is **{margin:.2f}%**, indicating a strong gross profitability level in this dataset."
        )
    elif margin >= 15:
        insights.append(
            f"Overall profit margin is **{margin:.2f}%**. Margin should be monitored alongside discounts and costs."
        )
    else:
        insights.append(
            f"Overall profit margin is **{margin:.2f}%**. Cost, pricing and discount strategy deserve attention."
        )

if units is not None and revenue is not None and units > 0:
    avg_realization = revenue / units
    insights.append(
        f"Average revenue realization per unit is approximately **{money(avg_realization)}**."
    )

if avg_order is not None:
    insights.append(
        f"Average order value is approximately **{money(avg_order)}** across {orders:,} unique orders."
    )

if "__product_name" in filtered.columns and revenue is not None:
    pr = group_metric(filtered, "product_name", "revenue", 100)
    if pr is not None and len(pr) > 0:
        top_product = pr.iloc[0]["Product"]
        top_value = pr.iloc[0]["Revenue"]
        share = top_value / revenue * 100 if revenue else None
        insights.append(
            f"Top revenue product is **{top_product}**, contributing approximately **{money(top_value)}**"
            + (f" ({share:.1f}% of revenue)." if share is not None else ".")
        )

if "__category" in filtered.columns and revenue is not None:
    cr = group_metric(filtered, "category", "revenue", 100)
    if cr is not None and len(cr) > 0:
        top_cat = cr.iloc[0]["Category"]
        top_cat_value = cr.iloc[0]["Revenue"]
        cat_share = top_cat_value / revenue * 100 if revenue else None
        insights.append(
            f"Top revenue category is **{top_cat}**"
            + (f", contributing {cat_share:.1f}% of revenue." if cat_share is not None else ".")
        )

if ad_spend not in (None, 0) and roas is not None:
    if roas >= 4:
        insights.append(f"Marketing efficiency looks strong with an estimated **{roas:.2f}x ROAS**.")
    elif roas < 2:
        insights.append(f"Estimated ROAS is **{roas:.2f}x**; marketing efficiency should be reviewed.")

if returns is not None and revenue:
    return_ratio = returns / revenue * 100
    insights.append(
        f"Return/refund value is approximately **{return_ratio:.2f}% of revenue** based on the available fields."
    )

if "__stock" in filtered.columns and "__minimum_stock" in filtered.columns:
    low = (
        pd.to_numeric(filtered["__stock"], errors="coerce")
        <= pd.to_numeric(filtered["__minimum_stock"], errors="coerce")
    ).sum()
    if low:
        insights.append(
            f"Inventory alert: **{int(low)}** record(s) are at or below the supplied minimum/reorder stock level."
        )

if not insights:
    insights.append(
        "Not enough recognised business fields were available to generate reliable financial insights."
    )

for i, text in enumerate(insights, start=1):
    st.markdown(
        f'<div class="insight-card"><b>{i}.</b> {text}</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# DATA QUALITY
# ============================================================

st.markdown('<div class="section-title">🔍 Data Quality & Reliability</div>', unsafe_allow_html=True)

quality = pd.DataFrame(
    {
        "Check": [
            "Rows analysed",
            "Columns analysed",
            "Missing cells",
            "Duplicate rows",
            "Detected business fields",
            "Date field available",
            "Revenue field available",
            "Profit field available",
            "Product field available",
            "Customer field available",
        ],
        "Result": [
            f"{len(filtered):,}",
            f"{len(raw_df.columns):,}",
            f"{int(raw_df.isna().sum().sum()):,}",
            f"{int(raw_df.duplicated().sum()):,}",
            f"{len(mapping):,}",
            "Yes" if "__order_date" in filtered.columns else "No",
            "Yes" if metric_available(filtered, "revenue") else "No",
            "Yes" if metric_available(filtered, "profit") else "No",
            "Yes" if "__product_name" in filtered.columns else "No",
            "Yes" if "__customer" in filtered.columns else "No",
        ],
    }
)
st.dataframe(quality, use_container_width=True, hide_index=True)


# ============================================================
# EXPORT DATA
# ============================================================

st.markdown('<div class="section-title">📤 Export Analysis</div>', unsafe_allow_html=True)

# User-friendly cleaned/export table.
export_df = filtered.copy()

# Remove internal columns and convert dates.
internal_cols = [c for c in export_df.columns if c.startswith("__")]
export_df = export_df.drop(columns=internal_cols, errors="ignore")

csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")

e1, e2 = st.columns(2)

with e1:
    st.download_button(
        "⬇️ Download Analysed CSV",
        data=csv_bytes,
        file_name="BizPilot_Analysed_Data.csv",
        mime="text/csv",
        use_container_width=True,
    )

with e2:
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Analysed Data")
        pd.DataFrame(det_rows).to_excel(
            writer,
            index=False,
            sheet_name="Detected Columns",
        )
        quality.to_excel(
            writer,
            index=False,
            sheet_name="Data Quality",
        )

    st.download_button(
        "⬇️ Download Analysis Excel",
        data=excel_buffer.getvalue(),
        file_name="BizPilot_Analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


# ============================================================
# PDF REPORT
# ============================================================


def _calculation_audit(work_df, revenue, cost, profit):
    """Return a transparent audit of the main financial calculations."""
    audit = {
        "sales_available": revenue is not None,
        "cost_available": cost is not None,
        "profit_available": profit is not None,
        "sales_minus_cost": None,
        "profit_matches_sales_minus_cost": None,
        "warning": None,
    }
    if revenue is not None and cost is not None:
        audit["sales_minus_cost"] = revenue - cost
    if revenue is not None and cost is not None and profit is not None:
        expected = revenue - cost
        audit["profit_matches_sales_minus_cost"] = bool(np.isclose(profit, expected, rtol=1e-8, atol=0.01))
        if not audit["profit_matches_sales_minus_cost"]:
            audit["warning"] = "Profit was recalculated from Sales − Total Cost because the source figures did not reconcile."
        elif cost > revenue and profit >= 0:
            audit["warning"] = "Source cost is higher than sales; the dataset indicates a loss unless the cost field is misclassified."
    return audit


def _inventory_summary(work_df):
    """Return one stock value per product where possible, avoiding double-counting
    stock repeated on every sales transaction."""
    if "__stock" not in work_df.columns:
        return None

    cols = ["__stock"]
    if "__product_name" in work_df.columns:
        cols.insert(0, "__product_name")
    if "__order_date" in work_df.columns:
        cols.append("__order_date")
    if "__minimum_stock" in work_df.columns:
        cols.append("__minimum_stock")

    inv = work_df[cols].copy()
    inv["__stock"] = pd.to_numeric(inv["__stock"], errors="coerce")
    inv = inv.dropna(subset=["__stock"])

    if inv.empty:
        return None

    if "__product_name" in inv.columns:
        inv["__product_name"] = inv["__product_name"].astype(str).str.strip()
        if "__order_date" in inv.columns:
            inv = inv.sort_values("__order_date")
        inv = inv.drop_duplicates("__product_name", keep="last")
    return inv


def _report_chart_path(fig, name):
    """Save a report chart to a real OS temp file.

    The previous implementation hard-coded /tmp, which fails on Windows
    deployments because /tmp may not exist. NamedTemporaryFile also keeps
    the file available long enough for ReportLab to read it.
    """
    suffix = "_" + re.sub(r"[^a-zA-Z0-9_-]+", "_", str(name)) + ".png"
    fd, path = tempfile.mkstemp(prefix="bizpilot_", suffix=suffix)
    os.close(fd)
    try:
        fig.savefig(path, dpi=170, bbox_inches="tight", format="png")
    finally:
        plt.close(fig)
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise RuntimeError(f"Chart file could not be created: {path}")
    return path


def _make_report_charts(filtered_df):
    """Create only the charts that directly support business decisions."""
    chart_paths = {}

    # Product revenue
    if "__product_name" in filtered_df.columns and metric_available(filtered_df, "revenue"):
        pr = group_metric(filtered_df, "product_name", "revenue", 8)
        if pr is not None and not pr.empty:
            fig, ax = plt.subplots(figsize=(9.4, 4.2))
            d = pr.sort_values("Revenue")
            ax.barh(d["Product"].astype(str), d["Revenue"])
            ax.set_title("Top Products by Sales", fontweight="bold")
            ax.set_xlabel("Sales / Revenue")
            ax.grid(axis="x", alpha=0.18)
            fig.tight_layout()
            chart_paths["product_revenue"] = _report_chart_path(fig, "product_revenue")

    # Product profit — important because highest sales is not always highest benefit
    if "__product_name" in filtered_df.columns and metric_available(filtered_df, "profit"):
        pp = group_metric(filtered_df, "product_name", "profit", 8)
        if pp is not None and not pp.empty:
            fig, ax = plt.subplots(figsize=(9.4, 4.2))
            d = pp.sort_values("Profit")
            ax.barh(d["Product"].astype(str), d["Profit"])
            ax.set_title("Top Products by Profit", fontweight="bold")
            ax.set_xlabel("Profit / Loss")
            ax.grid(axis="x", alpha=0.18)
            fig.tight_layout()
            chart_paths["product_profit"] = _report_chart_path(fig, "product_profit")

    # Monthly trend
    if "__order_date" in filtered_df.columns and metric_available(filtered_df, "revenue"):
        trend = filtered_df.dropna(subset=["__order_date", "__revenue"]).copy()
        if not trend.empty:
            monthly = (
                trend.assign(Month=trend["__order_date"].dt.to_period("M").astype(str))
                .groupby("Month", as_index=False)["__revenue"].sum()
            )
            if len(monthly) >= 2:
                fig, ax = plt.subplots(figsize=(9.4, 4.2))
                ax.plot(monthly["Month"], monthly["__revenue"], marker="o", linewidth=2)
                ax.set_title("Monthly Sales Trend", fontweight="bold")
                ax.set_ylabel("Sales / Revenue")
                ax.tick_params(axis="x", rotation=35)
                ax.grid(alpha=0.18)
                fig.tight_layout()
                chart_paths["monthly_trend"] = _report_chart_path(fig, "monthly_trend")

    # Category mix / pie chart
    if "__category" in filtered_df.columns and metric_available(filtered_df, "revenue"):
        cr = group_metric(filtered_df, "category", "revenue", 8)
        if cr is not None and len(cr) >= 2:
            fig, ax = plt.subplots(figsize=(6.8, 4.7))
            ax.pie(cr["Revenue"], labels=cr["Category"].astype(str), autopct="%1.0f%%",
                   startangle=90, wedgeprops=dict(width=0.42))
            ax.set_title("Sales Mix by Category", fontweight="bold")
            fig.tight_layout()
            chart_paths["category_mix"] = _report_chart_path(fig, "category_mix")

    # Remaining stock
    inv = _inventory_summary(filtered_df)
    if inv is not None and "__product_name" in inv.columns:
        d = inv.sort_values("__stock").head(8)
        if not d.empty:
            fig, ax = plt.subplots(figsize=(9.4, 4.2))
            ax.barh(d["__product_name"].astype(str), d["__stock"])
            ax.set_title("Products with Lowest Remaining Stock", fontweight="bold")
            ax.set_xlabel("Units Remaining")
            ax.grid(axis="x", alpha=0.18)
            fig.tight_layout()
            chart_paths["inventory"] = _report_chart_path(fig, "inventory")

    return chart_paths


def _report_business_actions(filtered_df, revenue, cost, profit, margin, units,
                             discount, returns, ad_spend, shipping):
    actions = []

    if profit is not None:
        if profit < 0:
            actions.append(
                f"Loss control: the analysed data shows a loss of {money(abs(profit))}. "
                "Management should review selling prices, unit costs, discounts and high-cost products."
            )
        else:
            actions.append(
                f"Profitability: the analysed data shows {money(profit)} profit "
                f"with a {pct(margin)} margin. Protect high-margin products and review low-margin items."
            )

    if "__product_name" in filtered_df.columns and revenue is not None:
        pr = group_metric(filtered_df, "product_name", "revenue", 100)
        if pr is not None and len(pr):
            top = pr.iloc[0]
            share = (top["Revenue"] / revenue * 100) if revenue else None
            actions.append(
                f"Growth opportunity: {top['Product']} is the leading revenue product"
                + (f" at about {share:.1f}% of analysed sales." if share is not None else ".")
                + " Consider protecting its availability and testing profitable upsell/cross-sell opportunities."
            )

    inv = _inventory_summary(filtered_df)
    if inv is not None:
        remaining = float(inv["__stock"].sum())
        low_count = None
        if "__minimum_stock" in inv.columns:
            mins = pd.to_numeric(inv["__minimum_stock"], errors="coerce")
            low_count = int((inv["__stock"] <= mins).fillna(False).sum())
        actions.append(
            f"Inventory position: approximately {number(remaining)} units remain in the supplied stock data."
            + (f" {low_count} product(s) are at/below the reorder level." if low_count is not None else "")
            + " Prioritise replenishment for fast-moving low-stock products."
        )

    if discount is not None and revenue not in (None, 0):
        ratio = discount / revenue * 100
        if ratio >= 10:
            actions.append(
                f"Margin risk: discounts are about {ratio:.1f}% of analysed revenue. "
                "Review discount-heavy products and set minimum-margin rules."
            )

    if returns is not None and revenue not in (None, 0):
        ratio = returns / revenue * 100
        if ratio >= 5:
            actions.append(
                f"Return risk: returns/refunds are about {ratio:.1f}% of revenue. "
                "Investigate the products, customers or periods driving returns."
            )

    if ad_spend not in (None, 0) and revenue is not None:
        roas_value = revenue / ad_spend
        actions.append(
            f"Marketing efficiency: tracked revenue is {roas_value:.2f}× ad spend. "
            "Compare this with product-level margin before increasing campaign budgets."
        )

    if not actions:
        actions.append(
            "The available dataset does not contain enough reliable financial or inventory fields "
            "to produce stronger business recommendations."
        )
    return actions


def build_pdf():
    """Build a clean 2–3 page management report with large readable text and decision charts."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=14 * mm, leftMargin=14 * mm,
        topMargin=12 * mm, bottomMargin=13 * mm,
        title="BizPilot Professional Business Analysis Report",
        author="BizPilot",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "BizTitleV8", parent=styles["Title"], fontName=REPORT_BOLD,
        alignment=TA_CENTER, fontSize=22, leading=26,
        textColor=colors.HexColor("#0F172A"), spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        "BizSubV8", parent=styles["Normal"], fontName=REPORT_FONT,
        alignment=TA_CENTER, fontSize=9.5, leading=12,
        textColor=colors.HexColor("#64748B"), spaceAfter=10,
    )
    heading = ParagraphStyle(
        "BizHeadingV8", parent=styles["Heading2"], fontName=REPORT_BOLD,
        fontSize=15, leading=18, textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=5, spaceAfter=7,
    )
    body = ParagraphStyle(
        "BizBodyV8", parent=styles["BodyText"], fontName=REPORT_FONT,
        fontSize=11.2, leading=16, textColor=colors.HexColor("#334155"),
        spaceAfter=2,
    )
    body_bold = ParagraphStyle(
        "BizBodyBoldV6", parent=body, fontName=REPORT_BOLD,
    )
    small = ParagraphStyle(
        "BizSmallV8", parent=styles["BodyText"], fontName=REPORT_FONT,
        fontSize=9.2, leading=12, textColor=colors.HexColor("#64748B"),
    )
    card_label = ParagraphStyle(
        "CardLabelV8", parent=styles["Normal"], fontName=REPORT_BOLD,
        alignment=TA_CENTER, fontSize=8.8, leading=11,
        textColor=colors.HexColor("#64748B"),
    )
    card_value = ParagraphStyle(
        "CardValueV8", parent=styles["Normal"], fontName=REPORT_BOLD,
        alignment=TA_CENTER, fontSize=15.5, leading=19,
        textColor=colors.HexColor("#0F172A"),
    )

    # ---- Metrics ----
    product_count = None
    if "__product_name" in filtered.columns:
        names = filtered["__product_name"].astype(str).str.strip()
        names = names.replace({"": np.nan, "nan": np.nan, "None": np.nan})
        product_count = names.nunique(dropna=True)

    inv = _inventory_summary(filtered)
    stock_remaining = float(inv["__stock"].sum()) if inv is not None else None
    low_stock = None
    if inv is not None and "__minimum_stock" in inv.columns:
        mins = pd.to_numeric(inv["__minimum_stock"], errors="coerce")
        low_stock = int((inv["__stock"] <= mins).fillna(False).sum())

    actions = _report_business_actions(
        filtered, revenue, cost, profit, margin, units,
        discount, returns, ad_spend, shipping
    )
    charts = _make_report_charts(filtered)
    calc_audit = _calculation_audit(filtered, revenue, cost, profit)

    top_product = None
    top_product_sales = None
    top_profit_product = None
    top_profit_value = None
    if "__product_name" in filtered.columns:
        if metric_available(filtered, "revenue"):
            pr = group_metric(filtered, "product_name", "revenue", 100)
            if pr is not None and not pr.empty:
                top_product, top_product_sales = str(pr.iloc[0]["Product"]), float(pr.iloc[0]["Revenue"])
        if metric_available(filtered, "profit"):
            pp = group_metric(filtered, "product_name", "profit", 100)
            if pp is not None and not pp.empty:
                top_profit_product, top_profit_value = str(pp.iloc[0]["Product"]), float(pp.iloc[0]["Profit"])

    period = "Available data"
    if "__order_date" in filtered.columns and filtered["__order_date"].notna().any():
        period = f"{filtered['__order_date'].min().strftime('%d %b %Y')} – {filtered['__order_date'].max().strftime('%d %b %Y')}"

    story = []

    # ========================================================
    # PAGE 1 — EXECUTIVE SUMMARY
    # ========================================================
    story.append(Paragraph("BizPilot", title_style))
    story.append(Paragraph("Business Performance Report", ParagraphStyle(
        "ReportTitle2", parent=title_style, fontSize=15, leading=18,
        textColor=colors.HexColor("#334155"), spaceAfter=3)))
    story.append(Paragraph(
        f"{get_business_name() or 'Business'}  •  {period}", sub_style
    ))

    cards = [
        ("SALES / REVENUE", money(revenue)),
        ("TOTAL COST", money(cost)),
        ("PROFIT / LOSS", money(profit)),
        ("PROFIT MARGIN", pct(margin)),
        ("TOTAL PRODUCTS", number(product_count)),
        ("UNITS SOLD", number(units)),
        ("STOCK REMAINING", number(stock_remaining)),
        ("LOW STOCK", number(low_stock)),
    ]
    card_rows = []
    for i in range(0, 8, 4):
        card_rows.append([Paragraph(cards[j][0], card_label) for j in range(i, i + 4)])
        card_rows.append([Paragraph(cards[j][1], card_value) for j in range(i, i + 4)])
    kt = Table(card_rows, colWidths=[44 * mm] * 4, rowHeights=[9 * mm, 14 * mm, 9 * mm, 14 * mm],
               hAlign="CENTER")
    kt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(kt)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Business Summary", heading))
    summary = []
    if revenue is not None:
        summary.append(f"Sales: <b>{money(revenue)}</b>")
    if profit is not None:
        summary.append((f"Profit: <b>{money(profit)}</b>" if profit >= 0
                        else f"Loss: <b>{money(abs(profit))}</b>"))
    if margin is not None:
        summary.append(f"Margin: <b>{pct(margin)}</b>")
    if product_count is not None:
        summary.append(f"Products: <b>{number(product_count)}</b>")
    if stock_remaining is not None:
        summary.append(f"Stock remaining: <b>{number(stock_remaining)} units</b>")
    story.append(Paragraph("  •  ".join(summary) if summary else "Reliable summary metrics were not available.", body))

    basis = []
    if revenue is not None and cost is not None:
        basis.append(f"Profit = Sales − Cost = {money(revenue)} − {money(cost)} = {money(profit)}")
    if margin is not None:
        basis.append(f"Margin = Profit ÷ Sales × 100 = {pct(margin)}")
    if stock_remaining is not None:
        basis.append(f"Stock = current/closing stock or Opening + Purchases − Sold = {number(stock_remaining)} units")
    if basis:
        story.append(Paragraph("Calculation basis: " + "  •  ".join(basis), small))
    if calc_audit.get("warning"):
        story.append(Paragraph("<b>Data check:</b> " + calc_audit["warning"], small))

    story.append(Paragraph("Product Performance", heading))
    if top_product is not None:
        share = (top_product_sales / revenue * 100) if revenue else None
        text = f"<b>Best-selling:</b> {top_product} — {money(top_product_sales)}"
        if share is not None:
            text += f" ({share:.1f}% of sales)"
        story.append(Paragraph(text, body))
    if top_profit_product is not None:
        story.append(Paragraph(
            f"<b>Highest-profit:</b> {top_profit_product} — {money(top_profit_value)}", body))
    if top_product is None and top_profit_product is None:
        story.append(Paragraph("Product-level performance is not available from the supplied data.", body))

    # Compact product decision table: only the most useful business fields.
    product_table_added = False
    if "__product_name" in filtered.columns and metric_available(filtered, "revenue"):
        prod = filtered.copy()
        prod["__product_name"] = prod["__product_name"].astype(str).str.strip()
        prod = prod[prod["__product_name"].ne("") & prod["__product_name"].ne("nan")]
        if not prod.empty:
            rows = []
            grouped = prod.groupby("__product_name", as_index=False).agg(
                Revenue=("__revenue", "sum"),
                Units=("__quantity", "sum") if "__quantity" in prod.columns else ("__revenue", "size"),
            )
            if "__profit" in prod.columns:
                gp = prod.groupby("__product_name")["__profit"].sum()
                grouped["Profit"] = grouped["__product_name"].map(gp)
                grouped["Margin"] = np.where(
                    grouped["Revenue"] != 0,
                    grouped["Profit"] / grouped["Revenue"] * 100,
                    np.nan,
                )
            else:
                grouped["Profit"] = np.nan
                grouped["Margin"] = np.nan
            inv_prod = _inventory_summary(prod)
            if inv_prod is not None and "__product_name" in inv_prod.columns:
                stock_map = inv_prod.groupby("__product_name")["__stock"].sum()
                grouped["Stock"] = grouped["__product_name"].map(stock_map)
            else:
                grouped["Stock"] = np.nan
            grouped = grouped.sort_values("Revenue", ascending=False).head(8)
            rows.append([Paragraph("Product", card_label), Paragraph("Sales", card_label),
                         Paragraph("Profit", card_label), Paragraph("Margin", card_label),
                         Paragraph("Stock", card_label)])
            for _, r in grouped.iterrows():
                rows.append([
                    Paragraph(str(r["__product_name"])[:28], small),
                    Paragraph(money(r["Revenue"]), small),
                    Paragraph(money(r["Profit"]), small),
                    Paragraph(pct(r["Margin"]), small),
                    Paragraph(number(r["Stock"]) if not pd.isna(r["Stock"]) else "N/A", small),
                ])
            pt = Table(rows, colWidths=[64*mm, 29*mm, 29*mm, 24*mm, 24*mm], repeatRows=1)
            pt.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#E2E8F0")),
                ("BOX", (0,0), (-1,-1), 0.6, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0,0), (-1,-1), 0.35, colors.HexColor("#E2E8F0")),
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("LEFTPADDING", (0,0), (-1,-1), 5),
                ("RIGHTPADDING", (0,0), (-1,-1), 5),
                ("TOPPADDING", (0,0), (-1,-1), 4),
                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ]))
            story.append(Paragraph("Product Performance", heading))
            story.append(pt)
            product_table_added = True

    story.append(Paragraph("Recommended Next Steps", heading))
    for item in actions[:4]:
        story.append(Paragraph("• " + item, body))

    story.append(Spacer(1, 5))
    story.append(Paragraph(
        "The report uses only reliable fields available in the uploaded data. Missing values are shown as N/A; no unavailable figures are invented.",
        small
    ))

    # ========================================================
    # PAGE 2 — PRODUCT CHARTS
    # ========================================================
    product_chart_added = False
    if "product_revenue" in charts or "product_profit" in charts:
        story.append(PageBreak())
        story.append(Paragraph("Product Performance Charts", heading))
        if "product_revenue" in charts:
            story.append(Paragraph("Sales by Product", ParagraphStyle(
                "ChartHeadSalesV8", parent=heading, fontSize=12, leading=14, spaceBefore=1, spaceAfter=4)))
            story.append(RLImage(charts["product_revenue"], width=176 * mm, height=86 * mm))
            story.append(Spacer(1, 6))
            product_chart_added = True
        if "product_profit" in charts:
            story.append(Paragraph("Profit by Product", ParagraphStyle(
                "ChartHeadProfitV8", parent=heading, fontSize=12, leading=14, spaceBefore=1, spaceAfter=4)))
            story.append(RLImage(charts["product_profit"], width=176 * mm, height=86 * mm))
            product_chart_added = True

    # ========================================================
    # PAGE 3 — TREND + CATEGORY + INVENTORY
    # ========================================================
    remaining_charts = [k for k in ["monthly_trend", "category_mix", "inventory"] if k in charts]
    if remaining_charts:
        story.append(PageBreak())
        story.append(Paragraph("Trend, Category & Stock", heading))
        if "monthly_trend" in charts:
            story.append(RLImage(charts["monthly_trend"], width=174 * mm, height=72 * mm))
            story.append(Spacer(1, 6))
        if "category_mix" in charts:
            story.append(Paragraph("Sales Mix", ParagraphStyle(
                "MiniHeadCatV8", parent=heading, fontSize=12, leading=14, spaceBefore=1, spaceAfter=3)))
            story.append(RLImage(charts["category_mix"], width=92 * mm, height=60 * mm))
            story.append(Spacer(1, 4))
        if "inventory" in charts:
            story.append(Paragraph("Remaining Stock", ParagraphStyle(
                "MiniHeadInvV8", parent=heading, fontSize=12, leading=14, spaceBefore=1, spaceAfter=3)))
            story.append(RLImage(charts["inventory"], width=174 * mm, height=68 * mm))

        story.append(Spacer(1, 5))
        if stock_remaining is not None:
            stock_line = f"<b>Stock remaining:</b> {number(stock_remaining)} units"
            if low_stock is not None:
                stock_line += f"  •  <b>Low stock:</b> {number(low_stock)} products"
            story.append(Paragraph(stock_line, body))

    chart_files = list(charts.values())
    try:
        doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
        return buffer.getvalue()
    finally:
        for chart_file in chart_files:
            try:
                if chart_file and os.path.isfile(chart_file):
                    os.remove(chart_file)
            except OSError:
                pass


st.markdown('<div class="section-title">📄 Final Professional Report</div>', unsafe_allow_html=True)

if st.button("Generate Final PDF Report", type="primary", use_container_width=True):
    try:
        with st.spinner("Generating professional PDF report..."):
            pdf_bytes = build_pdf()

        st.success("Final PDF report is ready.")
        st.download_button(
            "⬇️ Download Final BizPilot PDF Report",
            data=pdf_bytes,
            file_name="BizPilot_Final_Analysis_Report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    except Exception as e:
        st.error(f"PDF report generation failed: {e}")
        st.caption("Tip: chart files are created in the system temporary folder automatically; no manual /tmp folder is required.")


# ============================================================
# END
# ============================================================

st.markdown("---")
st.caption(
    "BizPilot • Manage • Analyse • Grow • Automatic Business Data Intelligence"
)
