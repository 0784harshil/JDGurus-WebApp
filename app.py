from flask import Flask, jsonify, render_template, request, Response
from flask_cors import CORS
import pyodbc
import firebase_admin
from firebase_admin import credentials, auth, firestore
from datetime import datetime, timedelta
import socket
import requests
import concurrent.futures
import pandas as pd
import numpy as np
import json
import time
import re
from mlxtend.frequent_patterns import apriori, association_rules
from sqlalchemy import text  # Add this import
from datetime import date, datetime
from decimal import Decimal

# Import the employee_performance blueprint (assumed to be in a separate file)
from employee_performance import employee_performance_bp

# ------------------------------------------------------------------------------
# App Setup & Configuration
# ------------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

# Register blueprint for employee performance
app.register_blueprint(employee_performance_bp)

# Define connection string for SQL Server
server = 'DESKTOP-ACJEA5K\\PCAMERICA'  # Your server name
database = 'cresqlp'                   # Your database name
connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;'

def get_db_connection():
    """Establish and return a database connection."""
    conn = pyodbc.connect(connection_string)
    return conn

# ------------------------------------------------------------------------------
# Firebase Initialization
# ------------------------------------------------------------------------------
cred = credentials.Certificate("firebase-adminsdk.json")  # Ensure this file is secured
firebase_admin.initialize_app(cred)
db = firestore.client()

# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------
def to_bit(value):
    """Convert a value to bit (1 or 0) for boolean fields."""
    if isinstance(value, str):
        return 1 if value.lower() == 'true' else 0
    return 1 if value else 0

def send_zpl_to_printer(ip_address, zpl_code):
    """Send ZPL code to a Zebra printer at the given IP address."""
    try:
        printer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        printer_socket.connect((ip_address, 9100))  # Default Zebra port
        printer_socket.sendall(zpl_code.encode('utf-8'))
        printer_socket.close()
        return "Print command sent successfully."
    except Exception as e:
        return f"Error sending print command: {e}"

def get_existing_items():
    """Query local DB to get existing items (used in Firebase sync)."""
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT ItemNum, ItemName, Cost, Price FROM Inventory")
    items = cursor.fetchall()
    connection.close()
    return [{'ItemNum': item[0], 'ItemName': item[1], 'Cost': item[2], 'Price': item[3]} for item in items]

def fetch_inventory_data():
    """Fetch inventory data from the database."""
    with pyodbc.connect(connection_string) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT TOP 100 itemNum, itemName, cost, price FROM Inventory")
        rows = cursor.fetchall()
        inventory_data = []
        for row in rows:
            item = {
                'itemNum': row[0],
                'itemName': row[1],
                'cost': row[2],
                'price': row[3]
            }
            inventory_data.append(item)
    return inventory_data


# ------------------------------------------------------------------------------
# Employee Performance API
# ------------------------------------------------------------------------------
@app.route('/api/employee-performance', methods=['GET'])
def get_employee_performance():
    """
    Returns employee performance metrics from the 'employee' table.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT 
                Cashier_ID,
                EmpName,
                Dept_ID,
                Hourly_Wage,
                TimeWorkedThisPeriod,
                Current_Cash,
                CreateDate
            FROM employee
            ORDER BY CreateDate DESC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        if not rows:
            return jsonify({"message": "No employee performance data found"}), 404

        performance_data = [
            {
                "Cashier_ID": row[0],
                "EmpName": row[1],
                "Dept_ID": row[2],
                "Hourly_Wage": float(row[3]) if row[3] is not None else 0.0,
                "TimeWorkedThisPeriod": float(row[4]) if row[4] is not None else 0.0,
                "Current_Cash": float(row[5]) if row[5] is not None else 0.0,
                "CreateDate": row[6].strftime('%Y-%m-%d %H:%M:%S') if row[6] is not None else None
            }
            for row in rows
        ]
        conn.close()
        return jsonify(performance_data)
    except Exception as e:
        print("Error in /api/employee-performance:", str(e))
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------------------------
# Invoice Totals & Invoice Details APIs
# ------------------------------------------------------------------------------
@app.route('/api/invoice-totals', methods=['GET'])
def get_invoice_totals():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT 
                it.Invoice_Number, 
                it.Store_ID, 
                it.Grand_Total, 
                it.Total_Cost, 
                it.Total_Price, 
                it.Total_Tax1, 
                it.Total_Tax2, 
                it.Total_Tax3, 
                ct.Approval
            FROM invoice_totals it
            JOIN CC_Trans ct
                ON it.Invoice_Number = ct.CRENumber
            ORDER BY it.Invoice_Number DESC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        if not rows:
            return jsonify({"message": "No data found"}), 404

        invoice_totals = [
            {
                "Invoice_Number": row[0],
                "Store_ID": row[1],
                "Grand_Total": float(row[2]) if row[2] is not None else 0.0,
                "Total_Cost": float(row[3]) if row[3] is not None else 0.0,
                "Total_Price": float(row[4]) if row[4] is not None else 0.0,
                "Total_Tax1": float(row[5]) if row[5] is not None else 0.0,
                "Total_Tax2": float(row[6]) if row[6] is not None else 0.0,
                "Total_Tax3": float(row[7]) if row[7] is not None else 0.0,
                "Approval": row[8]
            }
            for row in rows
        ]
        conn.close()
        return jsonify(invoice_totals)
    except Exception as e:
        print("Error in /api/invoice-totals:", str(e))
        return jsonify({"error": str(e)}), 500


@app.route('/api/invoices', methods=['GET'])
def get_invoices():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT invoice_number, total_price, DateTime FROM invoice_totals ORDER BY DateTime DESC")
        invoices = [{"invoice_number": row[0], "total_price": row[1], "DateTime": row[2]} for row in cursor.fetchall()]
        conn.close()
        return jsonify(invoices)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/invoice/<int:invoice_number>', methods=['GET'])
def get_invoice_details(invoice_number):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT diffitemname, quantity, priceper FROM invoice_itemized WHERE invoice_number = ?", (invoice_number,))
        items = [{"diffitemname": row[0], "quantity": row[1], "priceper": row[2]} for row in cursor.fetchall()]
        conn.close()
        return jsonify(items)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------------------------
# Dashboard & Inventory Insights APIs
# ------------------------------------------------------------------------------
@app.route('/api/dashboard/summary', methods=['GET'])
def dashboard_summary():
    """
    Returns a summary with overall total revenue and total inventory value.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT 
                (SELECT ISNULL(SUM(PricePer * Quantity), 0) FROM invoice_itemized) AS TotalRevenue,
                (SELECT ISNULL(SUM(In_Stock * Cost), 0) FROM inventory) AS TotalInventoryValue;
        """
        cursor.execute(query)
        result = cursor.fetchone()
        summary = {
            "TotalRevenue": float(result[0]),
            "TotalInventoryValue": float(result[1])
        }
        conn.close()
        return jsonify(summary)
    except Exception as e:
        print("Error in /api/dashboard/summary:", str(e))
        return jsonify({"error": str(e)}), 500




@app.route('/api/dashboard/top-selling-items', methods=['GET'])
def top_selling_items():
    """
    Returns the top 10 selling items based on total quantity sold and revenue.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT TOP 10
                i.ItemNum, i.ItemName, 
                SUM(ii.Quantity) AS TotalSold, 
                SUM(ii.Quantity * ii.PricePer) AS TotalRevenue
            FROM invoice_itemized ii
            JOIN inventory i ON ii.ItemNum = i.ItemNum
            GROUP BY i.ItemNum, i.ItemName
            ORDER BY TotalSold DESC;
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        items = [
            {
                "ItemNum": row[0],
                "ItemName": row[1],
                "TotalSold": float(row[2]),
                "TotalRevenue": float(row[3])
            }
            for row in rows
        ]
        conn.close()
        return jsonify(items)
    except Exception as e:
        print("Error in /api/dashboard/top-selling-items:", str(e))
        return jsonify({"error": str(e)}), 500
    

@app.route('/api/dashboard/item/<itemNum>', methods=['GET'])
def item_performance(itemNum):
    """
    Retrieves detailed performance data for a specific item.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT i.*, 
                   COALESCE(s.TotalSold, 0) AS TotalSold,
                   COALESCE(s.TotalRevenue, 0) AS TotalRevenue
            FROM inventory i
            LEFT JOIN (
                SELECT ItemNum, SUM(Quantity) AS TotalSold, SUM(Quantity * PricePer) AS TotalRevenue
                FROM invoice_itemized
                GROUP BY ItemNum
            ) s ON i.ItemNum = s.ItemNum
            WHERE i.ItemNum = ?;
        """
        cursor.execute(query, (itemNum,))
        row = cursor.fetchone()
        if row is None:
            conn.close()
            return jsonify({"error": "Item not found"}), 404

        columns = [column[0] for column in cursor.description]
        item = {columns[i]: row[i] for i in range(len(columns))}
        if 'TotalSold' in item and item['TotalSold'] is not None:
            item['TotalSold'] = float(item['TotalSold'])
        if 'TotalRevenue' in item and item['TotalRevenue'] is not None:
            item['TotalRevenue'] = float(item['TotalRevenue'])
        conn.close()
        return jsonify(item)
    except Exception as e:
        print("Error in /api/dashboard/item/<itemNum>:", str(e))
        return jsonify({"error": str(e)}), 500
    

@app.route('/api/dashboard/low-stock', methods=['GET'])
def low_stock():
    """
    Returns inventory items below reorder level along with sales information.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT i.ItemNum, i.ItemName, i.In_Stock, i.Reorder_Level,
                   COALESCE(s.TotalSold, 0) AS TotalSold,
                   COALESCE(s.TotalRevenue, 0) AS TotalRevenue
            FROM inventory i
            LEFT JOIN (
                SELECT ItemNum, SUM(Quantity) AS TotalSold, SUM(Quantity * PricePer) AS TotalRevenue
                FROM invoice_itemized
                GROUP BY ItemNum
            ) s ON i.ItemNum = s.ItemNum
            WHERE i.In_Stock < i.Reorder_Level;
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        items = [
            {
                "ItemNum": row[0],
                "ItemName": row[1],
                "In_Stock": float(row[2]),
                "Reorder_Level": float(row[3]),
                "TotalSold": float(row[4]),
                "TotalRevenue": float(row[5])
            }
            for row in rows
        ]
        conn.close()
        return jsonify(items)
    except Exception as e:
        print("Error in /api/dashboard/low-stock:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/api/dashboard/store-sales/<storeId>', methods=['GET'])
def store_sales(storeId):
    """
    Provides a sales summary for a given store.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT Store_ID, 
                   ISNULL(SUM(PricePer * Quantity), 0) AS TotalRevenue,
                   COUNT(DISTINCT Invoice_Number) AS TransactionCount
            FROM invoice_itemized
            WHERE Store_ID = ?
            GROUP BY Store_ID;
        """
        cursor.execute(query, (storeId,))
        row = cursor.fetchone()
        if row is None:
            conn.close()
            return jsonify({"error": "Store not found or no sales data available"}), 404
        summary = {
            "Store_ID": row[0],
            "TotalRevenue": float(row[1]),
            "TransactionCount": int(row[2])
        }
        conn.close()
        return jsonify(summary)
    except Exception as e:
        print("Error in /api/dashboard/store-sales/<storeId>:", str(e))
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------------------------
# Invoice Itemized, Inventory, and Customer APIs
# ------------------------------------------------------------------------------
@app.route('/api/invoice_itemized', methods=['GET'])
def get_invoice_itemized():
    try:
        with pyodbc.connect(connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Invoice_Itemized")
            rows = cursor.fetchall()
            invoice_list = []
            for row in rows:
                invoice_list.append({
                    'id': row[0],
                    'invoice_id': row[1],
                    'item_name': row[2],
                    'quantity': row[3],
                    'price': row[4]
                })
            return jsonify(invoice_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    try:
        with pyodbc.connect(connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT itemnum, itemname, In_Stock, QuantityRequired, price, cost FROM Inventory")
            rows = cursor.fetchall()
            inventory_list = []
            for row in rows:
                inventory_list.append({
                    'id': row[0],
                    'name': row[1],
                    'quantity': row[2],
                    'price': row[3],
                    'In_Stock' : row[4],
                    'cost': row[5]
                })
            return jsonify(inventory_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/customers', methods=['GET'])
def get_customers():
    try:
        with pyodbc.connect(connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Customer")
            rows = cursor.fetchall()
            customer_list = []
            for row in rows:
                customer_list.append({
                    'id': row[0],
                    'name': row[1],
                    'email': row[2],
                    'phone': row[3]
                })
            return jsonify(customer_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/setup', methods=['GET'])
def get_setup():
    try:
        with pyodbc.connect(connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Setup")
            rows = cursor.fetchall()
            setup_list = []
            for row in rows:
                setup_list.append({
                    'id': row[0],
                    'name': row[1],
                    'value': row[2]
                })
            return jsonify(setup_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------------------------
# Label Printing API
# ------------------------------------------------------------------------------
@app.route('/print_label', methods=['POST'])
def print_label():
    data = request.get_json()
    ip_address = data['ip_address']
    item_num = data['item_num']
    
    # Fetch item data from DB
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT itemname, price FROM inventory WHERE itemnum = ?", (item_num,))
    item = cursor.fetchone()
    
    if item:
        item_name, price = item
        zpl_code = f"""
        XA
        ^FO10,20^A0N,50,50^FD Product Name: {item_name} ^FS
        ^FO10,100^A0N,40,40^FD Barcode: ^FS
        ^BY3,3,100^FO10,150^BCN,100,Y,N,N^FD {item_num} ^FS
        ^FO10,200^A0N,50,50^FD Price: {price} ^FS
        ^XZ
        """
        result = send_zpl_to_printer(ip_address, zpl_code)
        return jsonify({"message": result}), 200
    else:
        return jsonify({"error": "Item not found"}), 404
    
# ------------------------------------------------------------------------------
# Other designs API
# ------------------------------------------------------------------------------

# Design 1: Uses cash_price and card_price
@app.route('/print_design1', methods=['POST'])
def print_design1():
    data = request.get_json()
    ip_address = data['ip_address']
    item_num = data['item_num']

    # Fetch item data from DB including cash and card prices
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT itemname, price FROM inventory WHERE itemnum = ?", (item_num,))
    row = cursor.fetchone()
    
    if row:
        item_name, price = row
        cash_price = float(price)
        card_price = round(cash_price * 1.05, 2)

        zpl_code = f"""
^XA
^PW457           ; Set label width (approx 2.25 inches at 203 dpi)
^LL254           ; Set label length (approx 1.25 inches at 203 dpi)

^CF0,30         ; Increase product name font to 30 dots tall
^FO10,15^FD{item_name}^FS

^FO10,45
^BY2,2,40       ; Adjust barcode module width, ratio and height
^BCN,40,Y,N,N^FD{item_num}^FS

^CF0,35         ; Increase price details font to 35 dots tall
^FO10,150^FDCash: ${cash_price}^FS
^FO240,150^FDCredit: ${card_price}^FS
^XZ
"""
        result = send_zpl_to_printer(ip_address, zpl_code)
        return jsonify({"message": result}), 200
    else:
        return jsonify({"error": "Item not found"}), 404


# Design 2: Uses a single price field
@app.route('/print_design2', methods=['POST'])
def print_design2():
    data = request.get_json()
    ip_address = data['ip_address']
    item_num = data['item_num']

    # Fetch item data from DB including price
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT itemname, price FROM inventory WHERE itemnum = ?", (item_num,))
    row = cursor.fetchone()
    
    if row:
        item_name, price = row
        price = float(price)
    
        zpl_code = f"""
^XA
^CF0,30            ; Increased font for product name to 30-dots height
^FO10,15^FD{item_name}^FS

^CF0,16            ; Slightly smaller font for the "Barcode:" label
^FO10,35^FD ^FS

^BY2,2,50         ; Set barcode module width and height (adjust if needed)
^FO10,50^BCN,50,Y,N,N^FD{item_num}^FS

^CF0,70            ; Increased font for the price to 30-dots height
^FO10,140^FD${price}^FS
^XZ

"""
        result = send_zpl_to_printer(ip_address, zpl_code)
        return jsonify({"message": result}), 200
    else:
        return jsonify({"error": "Item not found"}), 404

# Design 3: Uses cash_price and card_price
@app.route('/print_design3', methods=['POST'])
def print_design3():
    data = request.get_json()
    ip_address = data.get('ip_address')
    item_num = data.get('item_num')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT itemname, price FROM inventory WHERE itemnum = ?",
        (item_num,)
    )
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Item not found"}), 404

    item_name, price = row
    cash_price = float(price)
    credit_price = round(cash_price * 1.05, 2)

    zpl_code = f"""
^XA
^CF0,20
^FO10,15^FD{item_name}^FS

^BY2,2,50
^FO10,55^BCN,50,N,N,N^FD{item_num}^FS

^CF0,35
^FO10,150^FDCash: ${cash_price:.2f}^FS
^FO240,150^FDCredit: ${credit_price:.2f}^FS
^XZ
"""
    result = send_zpl_to_printer(ip_address, zpl_code)
    return jsonify({"message": result}), 200


# Design 4: Uses a single price field and prints a rotated barcode
@app.route('/print_design4', methods=['POST'])
def print_design4():
    data = request.get_json()
    ip_address = data['ip_address']
    item_num = data['item_num']

    # Fetch item data from DB including price
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT itemname, price FROM inventory WHERE itemnum = ?", (item_num,))
    row = cursor.fetchone()
    
    if row:
        item_name, price = row
        price = float(price)
        zpl_code = f"""
^XA
^CF0,30                        ; Set font for product name
^FO10,15^FD{item_name}^FS       ; Print product name at (10,10)

^CF0,60                       ; Use a slightly smaller font for the price
^FO10,70^FD${price}^FS           ; Print price at (10,50)

^BY2,2,80                      ; Set barcode parameters (module width, ratio, height)
^FO300,10                      ; Position the barcode on the right (X=300, Y=10)
^BCR,80,Y,N,N                  ; Print the barcode rotated 90° with height 80
^FD{item_num}^FS               ; Barcode data
^XZ
"""
        result = send_zpl_to_printer(ip_address, zpl_code)
        return jsonify({"message": result}), 200
    else:
        return jsonify({"error": "Item not found"}), 404

# Design 5: Uses a single price field with a formatted field block for item name and price
@app.route('/print_design5', methods=['POST'])
def print_design5():
    data = request.get_json()
    ip_address = data['ip_address']
    item_num = data['item_num']

    # Fetch item data from DB including price
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT itemname, price FROM inventory WHERE itemnum = ?", (item_num,))
    row = cursor.fetchone()
    
    if row:
        item_name, price = row
        price = float(price) 
        zpl_code = f"""
^XA
^CF0,30                              ; Set a smaller font for the item name
^FO0,30^FB457,1,0,L^FD{item_name}^FS    ; Left align the item name in a 457-dot wide field

^CF0,80                              ; Set a larger font for the price
^FO0,110^FB457,1,0,C^FD${price}^FS       ; Center the price below the item name
^XZ
"""
        result = send_zpl_to_printer(ip_address, zpl_code)
        return jsonify({"message": result}), 200
    else:
        return jsonify({"error": "Item not found"}), 404



@app.route('/mix-and-match', methods=['GET'])
def mix_and_match():
    query = """
    SELECT 
        ii.ItemNum AS [UPC], 
        ii.DiffItemName AS [ItemName], 
        it.Grand_Total AS [UnitPrice], 
        it.Total_Price AS [SalePrice], 
        ii.Quantity AS [ItemSold], 
        (it.Total_Price * ii.Quantity) AS [SaleAmount], 
        ISNULL(
            (SELECT TOP 1 i.price
             FROM inventory i
             JOIN kit_index k ON i.ItemNum = k.Kit_ID
             WHERE k.ItemNum = ii.ItemNum), 0) AS [MfgDeal] 
    FROM 
        Invoice_Itemized ii 
    JOIN 
        Invoice_Totals it ON ii.Invoice_Number = it.Invoice_Number 
    ORDER BY 
        UPC
    """

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query)

    # Fetch all results
    rows = cursor.fetchall()

    # Convert results to a list of dictionaries
    results = []
    for row in rows:
        results.append({
            'UPC': row.UPC,
            'Item Name': row.ItemName,
            'Unit Price': row.UnitPrice,
            'Sale Price': row.SalePrice,
            'Item Sold': row.ItemSold,
            'Sale Amount': row.SaleAmount,
            'Mfg.Deal': row.MfgDeal
        })

    cursor.close()
    conn.close()

    return jsonify(results)




# ------------------------------------------------------------------------------
# Kit Details API
# ------------------------------------------------------------------------------
@app.route('/api/kit_details', methods=['GET'])
def get_kit_details():
    try:
        with pyodbc.connect(connection_string) as conn:
            cursor = conn.cursor()
            query = '''
            SELECT
                DISTINCT(ii.Invoice_Number),
                ii.ItemNum AS [UPC],
                ii.DiffItemName AS [Item Name],
                i.Unit_Size AS [Unit Size],
                CAST(ii.PricePer AS DECIMAL(10, 2)) AS [Unit Price],
                CAST(
                    (ii.PricePer - ABS(((SELECT TOP 1 i.Price
                                         FROM inventory i
                                         WHERE i.ItemNum = k.Kit_ID)) / ii.Quantity))
                    AS DECIMAL(10, 2)
                ) AS [Sale Price],
                CAST(ii.Quantity AS INT) AS [Item Sold],  
                it.Total_Price AS [Sale Amount],
                CAST(ABS(i_mfg.Price) AS DECIMAL(10, 2)) AS [Mfg Deal]
            FROM Invoice_Itemized ii
            JOIN Kit_Index k ON k.ItemNum = ii.ItemNum
            JOIN Invoice_Totals it ON ii.Invoice_Number = it.Invoice_Number
            JOIN Inventory i ON i.ItemNum = ii.ItemNum
            LEFT OUTER JOIN (
                SELECT
                    i.Price,
                    k.ItemNum AS Kit_ItemNum
                FROM Inventory i
                JOIN Kit_Index k ON k.Kit_ID = i.ItemNum
            ) i_mfg ON i_mfg.Kit_ItemNum = ii.ItemNum
            WHERE ii.Invoice_Number IN (
                131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 371, 372, 373, 374, 375, 376, 377, 378, 379, 380, 381, 382, 383, 384, 385, 386, 387, 388, 468, 469, 470, 471, 472, 473, 474, 475, 476, 477, 478, 479, 480, 481, 482, 483, 484, 497, 498, 499, 500, 501, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511, 512, 513, 514, 515, 516, 517, 567, 568, 569, 570, 571, 572, 573, 574, 575, 576, 577, 578, 579, 630, 631, 632, 633, 634, 635, 636, 637, 638, 639, 640, 641, 642, 643, 644, 645, 646, 712, 713, 714, 715, 716, 717, 718, 719, 791, 792, 793, 794, 795, 796, 930, 931, 932, 933, 934, 935, 937, 939, 940, 956, 957, 958, 959, 960, 961, 962, 963, 1012, 1013, 1014, 1015, 1016, 1017, 1018, 1019, 1020, 1021, 1022, 1164, 1165, 1166, 1167, 1168, 1228, 1229, 1230, 1231, 1232, 1281, 1282, 1283, 1284, 1285, 1286, 1402, 1403, 1404, 1405, 1406, 1407, 1408, 1409, 1410, 1411)
            AND ii.ItemNum NOT IN ('76226', '76227', '76228', '76229', '76230', '76231', '76232', '76233', '76234', '76235', '76236', '76237', '76238', '76239', '76240', '76241', '76242', '76243', '76244', '76245', '76246', '76247', '76248', '76249', '76250', '76251', '76252', '76253', '76254', '76255', '76256', '76257', '76258', '76259', '76260', '76261', '76262')
            ORDER BY ii.Invoice_Number
            '''
            cursor.execute(query)
            rows = cursor.fetchall()
            kit_details_list = []
            for row in rows:
                kit_details_list.append({
                    'Invoice_Number': row[0],
                    'UPC': row[1],
                    'Item Name': row[2],
                    'Unit Size': row[3],
                    'Unit Price': row[4],
                    'Sale Price': row[5],
                    'Item Sold': row[6],
                    'Sale Amount': row[7],
                    'Mfg Deal': row[8]
                })
            return jsonify(kit_details_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------------------------
# Firebase Sync & Item APIs
# ------------------------------------------------------------------------------
@app.route('/api/sync_inventory', methods=['POST'])
def sync_inventory_to_firebase():
    try:
        inventory_data = fetch_inventory_data()
        for item in inventory_data:
            item['cost'] = float(item['cost'])
            item['price'] = float(item['price'])
            db.collection("Inventory").document(str(item['itemNum'])).set(item)
        return jsonify({"success": True, "message": "Data synced to Firebase successfully", "data": inventory_data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get_inventory', methods=['GET'])
def fetch_inventory():
    try:
        inventory_ref = db.collection("Inventory")
        docs = inventory_ref.stream()
        inventory_data = []
        for doc in docs:
            item = doc.to_dict()
            item['itemNum'] = doc.id
            inventory_data.append(item)
        return jsonify(inventory_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get_item/<string:item_num>', methods=['GET'])
def get_item(item_num):
    try:
        with pyodbc.connect(connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT itemName, cost, price FROM Inventory WHERE itemNum = ?", (item_num,))
            row = cursor.fetchone()
            if row:
                item_data = {
                    'itemName': row[0],
                    'cost': float(row[1]),
                    'price': float(row[2])
                }
                return jsonify(item_data), 200
            else:
                return jsonify({"error": "Item not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/add_item_to_firebase', methods=['POST'])
def add_item_to_firebase():
    try:
        item_data_list = request.json
        if not isinstance(item_data_list, list):
            return jsonify({"error": "Expected a list of items."}), 400

        results = []
        for item_data in item_data_list:
            if not isinstance(item_data, dict):
                return jsonify({"error": "Each item must be a dictionary."}), 400
            item_num = item_data.get('itemNum')
            item_name = item_data.get('itemName')
            if not item_num or not item_name:
                return jsonify({"error": "Item number and item name are required."}), 400
            cost_str = item_data.get('cost', '')
            price_str = item_data.get('price', '')
            if cost_str == '' or price_str == '':
                return jsonify({"error": "Cost and Price fields cannot be empty."}), 400
            try:
                cost = float(cost_str)
                price = float(price_str)
            except ValueError:
                return jsonify({"error": "Cost and Price must be valid numbers."}), 400
            item = {
                'itemNum': item_num,
                'itemName': item_name,
                'cost': cost,
                'price': price
            }
            db.collection("Inventory").document(str(item_num)).set(item)
            results.append({"itemNum": item_num, "status": "added"})
        return jsonify({"success": True, "results": results}), 201
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/get_item_details/<item_num>', methods=['GET'])
def get_item_details(item_num):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Inventory WHERE ItemNum = ?", (item_num,))
            item = cursor.fetchone()
            if item:
                item_details = {
                    "itemNum": item[0],
                    "itemName": item[1],
                    "storeID": item[2],
                    "cost": item[3],
                    "price": item[4],
                    "retailPrice": item[5],
                    "inStock": item[6],
                    "reorderLevel": item[7],
                    "reorderQuantity": item[8],
                    "invNumBarcodeLabels": item[9],
                    "tax1": item[10],
                    "tax2": item[11],
                    "tax3": item[12],
                    "vendorNumber": item[13],
                    "deptID": item[14],
                    "isKit": item[15],
                    "isModifier": item[16],
                    "numBoxes": item[17],
                }
                return jsonify(item_details), 200
            else:
                return jsonify({"error": "Item not found."}), 404
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/update_item_in_inventory/<item_num>', methods=['PUT'])
def update_item_in_inventory(item_num):
    try:
        item_data = request.json
        print("Incoming item data:", item_data)
        is_kit = to_bit(item_data.get('isKit', 'false'))
        is_modifier = to_bit(item_data.get('isModifier', 'false'))
        is_rental = to_bit(item_data.get('isRental', 'false'))
        use_bulk_pricing = to_bit(item_data.get('useBulkPricing', 'false'))
        print_ticket = to_bit(item_data.get('printTicket', 'false'))
        print_voucher = to_bit(item_data.get('printVoucher', 'false'))
        food_stampable = to_bit(item_data.get('foodStampable', 'false'))
        auto_weigh = to_bit(item_data.get('autoWeigh', 'false'))
        dirty = to_bit(item_data.get('dirty', 'false'))
        tear = to_bit(item_data.get('tear', 'false'))
        is_matrix_item = to_bit(item_data.get('isMatrixItem', 'false'))
        exclude_acct_limit = to_bit(item_data.get('excludeAcctLimit', 0))
        is_deleted = to_bit(item_data.get('isDeleted', 0))
        
        dept_id = item_data.get('deptID', 'NONE')
        if dept_id != 'NONE':
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM Departments WHERE Dept_ID = ?", (dept_id,))
                exists = cursor.fetchone()[0]
                if exists == 0:
                    return jsonify({"error": f"Dept_ID '{dept_id}' does not exist in Departments table."}), 400

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE Inventory SET
                    ItemName = COALESCE(?, ItemName),
                    Store_ID = COALESCE(?, Store_ID),
                    Cost = COALESCE(?, Cost),
                    Price = COALESCE(?, Price),
                    Retail_Price = COALESCE(?, Retail_Price),
                    In_Stock = COALESCE(?, In_Stock),
                    Reorder_Level = COALESCE(?, Reorder_Level),
                    Reorder_Quantity = COALESCE(?, Reorder_Quantity),
                    Tax_1 = COALESCE(?, Tax_1),
                    Tax_2 = COALESCE(?, Tax_2),
                    Tax_3 = COALESCE(?, Tax_3),
                    Vendor_Number = COALESCE(?, Vendor_Number),
                    Dept_ID = COALESCE(?, Dept_ID),
                    IsKit = COALESCE(?, IsKit),
                    IsModifier = COALESCE(?, IsModifier),
                    Kit_Override = COALESCE(?, Kit_Override),
                    Inv_Num_Barcode_Labels = COALESCE(?, Inv_Num_Barcode_Labels),
                    Use_Serial_Numbers = COALESCE(?, Use_Serial_Numbers),
                    Num_Bonus_Points = COALESCE(?, Num_Bonus_Points),
                    IsRental = COALESCE(?, IsRental),
                    Use_Bulk_Pricing = COALESCE(?, Use_Bulk_Pricing),
                    Print_Ticket = COALESCE(?, Print_Ticket),
                    Print_Voucher = COALESCE(?, Print_Voucher),
                    Num_Days_Valid = COALESCE(?, Num_Days_Valid),
                    IsMatrixItem = COALESCE(?, IsMatrixItem),
                    Vendor_Part_Num = COALESCE(?, Vendor_Part_Num),
                    Location = COALESCE(?, Location),
                    AutoWeigh = COALESCE(?, AutoWeigh),
                    numBoxes = COALESCE(?, numBoxes),
                    Dirty = COALESCE(?, Dirty),
                    Tear = COALESCE(?, Tear),
                    NumPerCase = COALESCE(?, NumPerCase),
                    FoodStampable = COALESCE(?, FoodStampable),
                    ReOrder_Cost = COALESCE(?, ReOrder_Cost),
                    Helper_ItemNum = COALESCE(?, Helper_ItemNum),
                    ItemName_Extra = COALESCE(?, ItemName_Extra),
                    Exclude_Acct_Limit = COALESCE(?, Exclude_Acct_Limit),
                    Check_ID = COALESCE(?, Check_ID),
                    Old_InStock = COALESCE(?, Old_InStock),
                    Last_Sold = COALESCE(?, Last_Sold),
                    Unit_Type = COALESCE(?, Unit_Type),
                    Unit_Size = COALESCE(?, Unit_Size),
                    Fixed_Tax = COALESCE(?, Fixed_Tax),
                    DOB = COALESCE(?, DOB),
                    Special_Permission = COALESCE(?, Special_Permission),
                    Prompt_Description = COALESCE(?, Prompt_Description),
                    Check_ID2 = COALESCE(?, Check_ID2),
                    Count_This_Item = COALESCE(?, Count_This_Item),
                    Transfer_Cost_Markup = COALESCE(?, Transfer_Cost_Markup),
                    Print_On_Receipt = COALESCE(?, Print_On_Receipt),
                    Transfer_Markup_Enabled = COALESCE(?, Transfer_Markup_Enabled),
                    As_Is = COALESCE(?, As_Is),
                    InStock_Committed = COALESCE(?, InStock_Committed),
                    RequireCustomer = COALESCE(?, RequireCustomer),
                    PromptCompletionDate = COALESCE(?, PromptCompletionDate),
                    PromptInvoiceNotes = COALESCE(?, PromptInvoiceNotes),
                    Prompt_DescriptionOverDollarAmt = COALESCE(?, Prompt_DescriptionOverDollarAmt),
                    Exclude_From_Loyalty = COALESCE(?, Exclude_From_Loyalty),
                    BarTaxInclusive = COALESCE(?, BarTaxInclusive),
                    ScaleSingleDeduct = COALESCE(?, ScaleSingleDeduct),
                    GLNumber = COALESCE(?, GLNumber),
                    ModifierType = COALESCE(?, ModifierType),
                    Position = COALESCE(?, Position),
                    numberOfFreeToppings = COALESCE(?, numberOfFreeToppings),
                    ScaleItemType = COALESCE(?, ScaleItemType),
                    DiscountType = COALESCE(?, DiscountType),
                    AllowReturns = COALESCE(?, AllowReturns),
                    SuggestedDeposit = COALESCE(?, SuggestedDeposit),
                    Liability = COALESCE(?, Liability),
                    IsDeleted = COALESCE(?, IsDeleted),
                    ItemLocale = COALESCE(?, ItemLocale),
                    QuantityRequired = COALESCE(?, QuantityRequired),
                    AllowOnDepositInvoices = COALESCE(?, AllowOnDepositInvoices),
                    Import_Markup = COALESCE(?, Import_Markup),
                    PricePerMeasure = COALESCE(?, PricePerMeasure),
                    UnitMeasure = COALESCE(?, UnitMeasure),
                    ShipCompliantProductType = COALESCE(?, ShipCompliantProductType),
                    AlcoholContent = COALESCE(?, AlcoholContent),
                    AvailableOnline = COALESCE(?, AvailableOnline),
                    AllowOnFleetCard = COALESCE(?, AllowOnFleetCard),
                    DoughnutTax = COALESCE(?, DoughnutTax),
                    DisplayTaxInPrice = COALESCE(?, DisplayTaxInPrice),
                    NeverPrintInKitchen = COALESCE(?, NeverPrintInKitchen),
                    Tax_4 = COALESCE(?, Tax_4),
                    Tax_5 = COALESCE(?, Tax_5),
                    Tax_6 = COALESCE(?, Tax_6),
                    DisableInventoryUpload = COALESCE(?, DisableInventoryUpload),
                    InvoiceLimitQty = COALESCE(?, InvoiceLimitQty),
                    ItemCategory = COALESCE(?, ItemCategory),
                    IsRestrictedPerInvoice = COALESCE(?, IsRestrictedPerInvoice),
                    TagStatus = COALESCE(?, TagStatus)
                WHERE ItemNum = ?
            """, (
                item_data.get('itemName'), item_data.get('storeID'), item_data.get('cost'), item_data.get('price'),
                item_data.get('retailPrice'), item_data.get('inStock'), item_data.get('reorderLevel'),
                item_data.get('reorderQuantity'), item_data.get('tax1'), item_data.get('tax2'), item_data.get('tax3'),
                item_data.get('vendorNumber'), dept_id, is_kit, is_modifier, item_data.get('kitOverride'),
                item_data.get('invNumBarcodeLabels'), item_data.get('useSerialNumbers'), item_data.get('numBonusPoints'),
                is_rental, use_bulk_pricing, print_ticket, print_voucher, item_data.get('numDaysValid'),
                is_matrix_item, item_data.get('vendorPartNum'), item_data.get('location'), auto_weigh,
                item_data.get('numBoxes'), dirty, tear, item_data.get('numPerCase'), food_stampable,
                item_data.get('reOrderCost'), item_data.get('helperItemNum'), item_data.get('itemNameExtra'),
                exclude_acct_limit, item_data.get('checkID'), item_data.get('oldInStock'), item_data.get('lastSold'),
                item_data.get('unitType'), item_data.get('unitSize'), item_data.get('fixedTax'), item_data.get('dob'),
                item_data.get('specialPermission'), item_data.get('promptDescription'), item_data.get('checkID2'),
                item_data.get('countThisItem'), item_data.get('transferCostMarkup'), item_data.get('printOnReceipt'),
                item_data.get('transferMarkupEnabled'), item_data.get('asIs'), item_data.get('inStockCommitted'),
                item_data.get('requireCustomer'), item_data.get('promptCompletionDate'), item_data.get('promptInvoiceNotes'),
                item_data.get('promptDescriptionOverDollarAmt'), item_data.get('excludeFromLoyalty'),
                item_data.get('barTaxInclusive'), item_data.get('scaleSingleDeduct'), item_data.get('glNumber'),
                item_data.get('modifierType'), item_data.get('position'), item_data.get('numberOfFreeToppings'),
                item_data.get('scaleItemType'), item_data.get('discountType'), item_data.get('allowReturns'),
                item_data.get('suggestedDeposit'), item_data.get('liability'), is_deleted, item_data.get('itemLocale'),
                item_data.get('quantityRequired'), item_data.get('allowOnDepositInvoices'), item_data.get('importMarkup'),
                item_data.get('pricePerMeasure'), item_data.get('unitMeasure'), item_data.get('shipCompliantProductType'),
                item_data.get('alcoholContent'), item_data.get('availableOnline'), item_data.get('allowOnFleetCard'),
                item_data.get('doughnutTax'), item_data.get('displayTaxInPrice'), item_data.get('neverPrintInKitchen'),
                item_data.get('tax4'), item_data.get('tax5'), item_data.get('tax6'), item_data.get('disableInventoryUpload'),
                item_data.get('invoiceLimitQty'), item_data.get('itemCategory'), item_data.get('isRestrictedPerInvoice'),
                item_data.get('tagStatus'), item_num
            ))
            conn.commit()
        return jsonify({"success": True, "message": "Item updated successfully!"}), 200
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/label_inventory', methods=['GET'])
def get_inventory_for_label():
    try:
        with pyodbc.connect(connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ItemNum, ItemName, Cost, Price FROM Inventory")
            rows = cursor.fetchall()
            inventory_list = []
            for row in rows:
                inventory_list.append({
                    'id': row[0],
                    'itemNum': row[0],
                    'itemName': row[1],
                    'cost': row[2],
                    'price': row[3]
                })
            return jsonify(inventory_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/add_item_to_inventory', methods=['POST'])
def add_item_to_inventory():
    try:
        item_data = request.json
        print("Incoming item data:", item_data)
        is_kit = to_bit(item_data.get('isKit', 'false'))
        is_modifier = to_bit(item_data.get('isModifier', 'false'))
        is_rental = to_bit(item_data.get('isRental', 'false'))
        use_bulk_pricing = to_bit(item_data.get('useBulkPricing', 'false'))
        print_ticket = to_bit(item_data.get('printTicket', 'false'))
        print_voucher = to_bit(item_data.get('printVoucher', 'false'))
        food_stampable = to_bit(item_data.get('foodStampable', 'false'))
        auto_weigh = to_bit(item_data.get('autoWeigh', 'false'))
        dirty = to_bit(item_data.get('dirty', 'false'))
        tear = to_bit(item_data.get('tear', 'false'))
        is_matrix_item = to_bit(item_data.get('isMatrixItem', 'false'))
        exclude_acct_limit = to_bit(item_data.get('excludeAcctLimit', 0))
        is_deleted = to_bit(item_data.get('isDeleted', 0))
        
        dept_id = item_data.get('deptID', 'NONE')
        if dept_id != 'NONE':
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM Departments WHERE Dept_ID = ?", (dept_id,))
                exists = cursor.fetchone()[0]
                if exists == 0:
                    return jsonify({"error": f"Dept_ID '{dept_id}' does not exist in Departments table."}), 400

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO Inventory (
                    ItemName, Store_ID, Cost, Price, Retail_Price, In_Stock, Reorder_Level, Reorder_Quantity,
                    Tax_1, Tax_2, Tax_3, Vendor_Number, Dept_ID, IsKit, IsModifier, Kit_Override, 
                    Inv_Num_Barcode_Labels, Use_Serial_Numbers, Num_Bonus_Points, IsRental, Use_Bulk_Pricing,
                    Print_Ticket, Print_Voucher, Num_Days_Valid, IsMatrixItem, Vendor_Part_Num, Location, 
                    AutoWeigh, numBoxes, Dirty, Tear, NumPerCase, FoodStampable, ReOrder_Cost, Helper_ItemNum,
                    ItemName_Extra, Exclude_Acct_Limit, Check_ID, Old_InStock, Last_Sold, Unit_Type, Unit_Size,
                    Fixed_Tax, DOB, Special_Permission, Prompt_Description, Check_ID2, Count_This_Item, 
                    Transfer_Cost_Markup, Print_On_Receipt, Transfer_Markup_Enabled, As_Is, InStock_Committed,
                    RequireCustomer, PromptCompletionDate, PromptInvoiceNotes, Prompt_DescriptionOverDollarAmt, 
                    Exclude_From_Loyalty, BarTaxInclusive, ScaleSingleDeduct, GLNumber, ModifierType, Position,
                    numberOfFreeToppings, ScaleItemType, DiscountType, AllowReturns, SuggestedDeposit, Liability,
                    IsDeleted, ItemLocale, QuantityRequired, AllowOnDepositInvoices, Import_Markup, PricePerMeasure,
                    UnitMeasure, ShipCompliantProductType, AlcoholContent, AvailableOnline, AllowOnFleetCard, 
                    DoughnutTax, DisplayTaxInPrice, NeverPrintInKitchen, Tax_4, Tax_5, Tax_6, DisableInventoryUpload,
                    InvoiceLimitQty, ItemCategory, IsRestrictedPerInvoice, TagStatus
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                item_data.get('itemName'), item_data.get('storeID'), item_data.get('cost'), item_data.get('price'),
                item_data.get('retailPrice'), item_data.get('inStock'), item_data.get('reorderLevel'),
                item_data.get('reorderQuantity'), item_data.get('tax1'), item_data.get('tax2'), item_data.get('tax3'),
                item_data.get('vendorNumber'), dept_id, is_kit, is_modifier, item_data.get('kitOverride'),
                item_data.get('invNumBarcodeLabels'), item_data.get('useSerialNumbers'), item_data.get('numBonusPoints'),
                is_rental, use_bulk_pricing, print_ticket, print_voucher, item_data.get('numDaysValid'),
                is_matrix_item, item_data.get('vendorPartNum'), item_data.get('location'), auto_weigh,
                item_data.get('numBoxes'), dirty, tear, item_data.get('numPerCase'), food_stampable,
                item_data.get('reOrderCost'), item_data.get('helperItemNum'), item_data.get('itemNameExtra'),
                exclude_acct_limit, item_data.get('checkID'), item_data.get('oldInStock'), item_data.get('lastSold'),
                item_data.get('unitType'), item_data.get('unitSize'), item_data.get('fixedTax'), item_data.get('dob'),
                item_data.get('specialPermission'), item_data.get('promptDescription'), item_data.get('checkID2'),
                item_data.get('countThisItem'), item_data.get('transferCostMarkup'), item_data.get('printOnReceipt'),
                item_data.get('transferMarkupEnabled'), item_data.get('asIs'), item_data.get('inStockCommitted'),
                item_data.get('requireCustomer'), item_data.get('promptCompletionDate'), item_data.get('promptInvoiceNotes'),
                item_data.get('promptDescriptionOverDollarAmt'), item_data.get('excludeFromLoyalty'),
                item_data.get('barTaxInclusive'), item_data.get('scaleSingleDeduct'), item_data.get('glNumber'),
                item_data.get('modifierType'), item_data.get('position'), item_data.get('numberOfFreeToppings'),
                item_data.get('scaleItemType'), item_data.get('discountType'), item_data.get('allowReturns'),
                item_data.get('suggestedDeposit'), item_data.get('liability'), is_deleted, item_data.get('itemLocale'),
                item_data.get('quantityRequired'), item_data.get('allowOnDepositInvoices'), item_data.get('importMarkup'),
                item_data.get('pricePerMeasure'), item_data.get('unitMeasure'), item_data.get('shipCompliantProductType'),
                item_data.get('alcoholContent'), item_data.get('availableOnline'), item_data.get('allowOnFleetCard'),
                item_data.get('doughnutTax'), item_data.get('displayTaxInPrice'), item_data.get('neverPrintInKitchen'),
                item_data.get('tax4'), item_data.get('tax5'), item_data.get('tax6'), item_data.get('disableInventoryUpload'),
                item_data.get('invoiceLimitQty'), item_data.get('itemCategory'), item_data.get('isRestrictedPerInvoice'),
                item_data.get('tagStatus')
            ))
            conn.commit()
        return jsonify({"success": True, "message": "Item added to inventory successfully!"}), 201
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return jsonify({"error": str(e)}), 500
    


@app.route('/add-item', methods=['POST'])
def add_item():
    data = request.get_json()
    # Get required fields from the request payload
    ItemNum = data.get('ItemNum')
    ItemName = data.get('ItemName')
    Cost = data.get('Cost')
    Price = data.get('Price')
    
    # Check if the department is provided; if not, use the default 'NONE'
    Dept_ID = data.get('Dept_ID') if data.get('Dept_ID') is not None else 'NONE'
    
    # Check if all required fields are provided
    if not all([ItemNum, ItemName, Cost, Price]):
        return jsonify({'error': 'Missing required fields'}), 400

    # Build the INSERT query. Adjust column names and order according to your schema.
    query = """
        INSERT INTO Inventory (
            ItemNum, ItemName, Store_ID, Cost,           -- 1-4
            Price, Retail_Price, In_Stock, Reorder_Level,  -- 5-8
            Reorder_Quantity, Tax_1, Tax_2, Tax_3,         -- 9-12
            Vendor_Number, Dept_ID, IsKit, IsModifier,     -- 13-16
            Kit_Override, Inv_Num_Barcode_Labels, Use_Serial_Numbers, Num_Bonus_Points,  -- 17-20
            IsRental, Use_Bulk_Pricing, Print_Ticket, Print_Voucher,  -- 21-24
            Num_Days_Valid, IsMatrixItem, Vendor_Part_Num, Location, -- 25-28
            AutoWeigh, numBoxes, Dirty, Tear,             -- 29-32
            NumPerCase, FoodStampable, ReOrder_Cost, Helper_ItemNum,  -- 33-36
            ItemName_Extra, Exclude_Acct_Limit, Check_ID, Old_InStock,  -- 37-40
            Date_Created, ItemType, Prompt_Price, Prompt_Quantity, -- 41-44
            Inactive, Allow_BuyBack, Last_Sold, Unit_Type,  -- 45-48
            Unit_Size, Fixed_Tax, DOB, Special_Permission,  -- 49-52
            Prompt_Description, Check_ID2, Count_This_Item, Transfer_Cost_Markup,  -- 53-56
            Print_On_Receipt, Transfer_Markup_Enabled, As_Is, InStock_Committed, -- 57-60
            RequireCustomer, PromptCompletionDate, PromptInvoiceNotes, Prompt_DescriptionOverDollarAmt,  -- 61-64
            Exclude_From_Loyalty, BarTaxInclusive, ScaleSingleDeduct, GLNumber, -- 65-68
            ModifierType, Position, numberOfFreeToppings, ScaleItemType,  -- 69-72
            DiscountType, AllowReturns, SuggestedDeposit, Liability,  -- 73-76
            IsDeleted, ItemLocale, QuantityRequired, AllowOnDepositInvoices,  -- 77-80
            Import_Markup, PricePerMeasure, UnitMeasure, ShipCompliantProductType, -- 81-84
            AlcoholContent, AvailableOnline, AllowOnFleetCard, DoughnutTax,  -- 85-88
            DisplayTaxInPrice, NeverPrintInKitchen, Tax_4, Tax_5,  -- 89-92
            Tax_6, DisableInventoryUpload, InvoiceLimitQty, ItemCategory,  -- 93-96
            IsRestrictedPerInvoice, TagStatus              -- 97-98
        ) VALUES (
            ?, ?, ?, ?,                             -- 1-4
            ?, ?, ?, ?,                             -- 5-8
            ?, ?, ?, ?,                             -- 9-12
            ?, ?, ?, ?,                             -- 13-16
            ?, ?, ?, ?,                             -- 17-20
            ?, ?, ?, ?,                             -- 21-24
            ?, ?, ?, ?,                             -- 25-28
            ?, ?, ?, ?,                             -- 29-32
            ?, ?, ?, ?,                             -- 33-36
            ?, ?, ?, ?,                             -- 37-40
            ?, ?, ?, ?,                             -- 41-44
            ?, ?, ?, ?,                             -- 45-48
            ?, ?, ?, ?,                             -- 49-52
            ?, ?, ?, ?,                             -- 53-56
            ?, ?, ?, ?,                             -- 57-60
            ?, ?, ?, ?,                             -- 61-64
            ?, ?, ?, ?,                             -- 65-68
            ?, ?, ?, ?,                             -- 69-72
            ?, ?, ?, ?,                             -- 73-76
            ?, ?, ?, ?,                             -- 77-80
            ?, ?, ?, ?,                             -- 81-84
            ?, ?, ?, ?,                             -- 85-88
            ?, ?, ?, ?,                             -- 89-92
            ?, ?, ?, ?,                             -- 93-96
            ?, ?                                    -- 97-98
        )
    """

    # Prepare parameters with the user-supplied values and defaults.
    # Note: Here, we override Dept_ID with the provided value if any.
    params = [
        ItemNum, ItemName, 1001, Cost,            # 1-4
        Price, 0.00, 0.00, 0,                       # 5-8
        0, 0, 0, 0,                               # 9-12
        None, Dept_ID, 0, 0,                        # 13-16: Dept_ID is set here from the frontend if provided
        0.00, 0, 0, 0,                             # 17-20
        0, 0, 0, 0,                                # 21-24
        0, 0, 0, 0,                                # 25-28
        0, 0, 0, 0,                                # 29-32
        0, 0, 0, 0,                                # 33-36
        1, 0, 0, 0,                                # 37-40
        0, 1, 0, 0,                       # 41-44 (using SQL's GETDATE() for Date_Created)
        0, 0, None, 'UOM',                          # 45-48
        None, 0, None, 0,                           # 49-52
        0, 0, 0, 0,                                # 53-56
        0, 0, 0, 0,                                # 57-60
        0, None, None, 0,                           # 61-64
        0, 0, 0, None,                             # 65-68
        None, None, 0, None,                        # 69-72
        0, 0, 0, 0,                                # 73-76
        0, None, 0, 0,                             # 77-80
        0, 0, None, None,                          # 81-84
        0, 0, 0, 0,                                # 85-88
        0, 0, 0, 0,                                # 89-92
        0, 0, 0, 0,                                # 93-96
        0, None                                   # 97-98
    ]
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(query, params)
        connection.commit()
        return jsonify({'message': 'Item added successfully'}), 201
    except pyodbc.Error as e:
        error_message = str(e)
        print(f"Database error: {error_message}")
        return jsonify({'error': 'Database error', 'details': error_message}), 500
    finally:
        cursor.close()
        connection.close()





@app.route('/delete-item', methods=['DELETE'])
def delete_item():
    data = request.get_json()
    # Get the ItemNum from the request payload
    ItemNum = data.get('ItemNum')
    
    # Check if ItemNum is provided
    if not ItemNum:
        return jsonify({'error': 'Missing required field: ItemNum'}), 400

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Define the parameterized queries.
        query1 = "DELETE FROM Inventory WHERE ItemNum = ?"
        query2 = "DELETE FROM Inventory_BumpBarSettings WHERE ItemNum = ?"
        query4 = "DELETE FROM Inventory_AdditionalInfo WHERE ItemNum = ?"  # New query added
        query3 = "DELETE FROM Kit_Index WHERE ItemNum = ?"

        def run_query(query, params):
            try:
                cursor.execute(query, params)
                connection.commit()
                return cursor.rowcount > 0
            except pyodbc.Error as e:
                print(f"Error executing query: {query} with params {params} - {e}")
                return False

        # Attempt Query1.
        if run_query(query1, [ItemNum]):
            return jsonify({"message": "Inventory item deleted successfully."}), 200
        else:
            print("Query1 failed. Attempting Query2 and then retrying Query1.")
            # Attempt Query2.
            run_query(query2, [ItemNum])
            # Retry Query1.
            if run_query(query1, [ItemNum]):
                return jsonify({"message": "Dependent records deleted via Inventory_BumpBarSettings; Inventory item deleted successfully after retry."}), 200
            else:
                print("Query1 still failed after Query2. Attempting Query4 and then retrying Query1.")
                # Attempt Query4.
                run_query(query4, [ItemNum])
                if run_query(query1, [ItemNum]):
                    return jsonify({"message": "Dependent records deleted via Inventory_Extra; Inventory item deleted successfully after retry."}), 200
                else:
                    print("Query1 still failed after Query4. Attempting Query3 and then retrying Query1.")
                    # Attempt Query3.
                    run_query(query3, [ItemNum])
                    if run_query(query1, [ItemNum]):
                        return jsonify({"message": "Dependent records deleted via Kit_Index; Inventory item deleted successfully after final retry."}), 200
                    else:
                        return jsonify({"error": "All attempts failed. Inventory item could not be deleted."}), 500

    except pyodbc.Error as e:
        error_message = str(e)
        print(f"Database error: {error_message}")
        return jsonify({'error': 'Database error', 'details': error_message}), 500
    finally:
        cursor.close()
        connection.close()





# ------------------------------------------------------------------------------
# Firebase Items Fetch & Merge APIs
# ------------------------------------------------------------------------------
@app.route('/api/get_firebase_items', methods=['GET'])
def get_firebase_items():
    try:
        items_ref = db.collection('Inventory')
        docs = items_ref.stream()
        data = []
        for doc in docs:
            item_data = doc.to_dict()
            data.append({
                'itemNum': item_data.get('itemNum'),
                'itemName': item_data.get('itemName'),
                'cost': item_data.get('cost'),
                'price': item_data.get('price')
            })
        return jsonify({'data': data}), 200
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return jsonify({'error': str(e)}), 500




def fetch_items_from_firebase():
    """Fetch items from the Firebase endpoint."""
    response = requests.get('http://localhost:5000/api/get_firebase_items')
    if response.status_code != 200:
        raise Exception("Failed to fetch items from Firebase")
    return response.json().get('data', [])

def add_item_to_inventory(item_payload):
    """Send a POST request to add an item to the inventory."""
    response = requests.post('http://localhost:5000/add-item', json=item_payload)
    return response.status_code == 201, response.text



@app.route('/api/fetch_and_add_items', methods=['POST'])
def fetch_and_add_items():
    try:
        # Fetch items from Firebase
        fetched_items = fetch_items_from_firebase()
        print("Fetched items:", fetched_items)

        # Retrieve existing items and collect their item numbers for duplicate checking
        existing_items = get_existing_items()
        existing_item_nums = {item['ItemNum'] for item in existing_items}

        # Partition items into duplicates and unique items
        duplicate_items = [item for item in fetched_items if item.get('itemNum') in existing_item_nums]
        unique_items = [item for item in fetched_items if item.get('itemNum') not in existing_item_nums]

        failed_items = []
        # Process unique items: add each one individually
        for item in unique_items:
            item_payload = {
                'ItemNum': item.get('itemNum'),
                'ItemName': item.get('itemName'),
                'Cost': item.get('cost'),
                'Price': item.get('price'),
            }
            success, response_text = add_item_to_inventory(item_payload)
            if not success:
                failed_items.append(item_payload)
                print(f"Failed to add item: {item_payload}, Response: {response_text}")

        # Determine response based on results
        if failed_items:
            return jsonify({'error': 'Some items failed to add', 'failed_items': failed_items}), 500
        if duplicate_items:
            return jsonify({
                'warning': 'Some items already exist in the inventory and were skipped',
                'duplicate_items': duplicate_items
            }), 409

        return jsonify({'message': 'Items fetched and added to inventory successfully!'}), 201

    except Exception as e:
        print("Error occurred:", str(e))
        return jsonify({'error': str(e)}), 500





@app.route('/api/label_data', methods=['GET'])
def get_label_data():
    try:
        with pyodbc.connect(connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT itemNum, itemName, price FROM Inventory")
            rows = cursor.fetchall()
            label_data = []
            for row in rows:
                label_data.append({
                    'itemNum': row[0],
                    'itemName': row[1],
                    'price': row[2]
                })
            return jsonify(label_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------------------------
# Market Basket Analysis & Recommendation APIs
# ------------------------------------------------------------------------------
@app.route('/api/market_basket', methods=['GET'])
def market_basket_analysis():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT invoice_number, diffitemname FROM invoice_itemized")
        rows = cursor.fetchall()
        conn.close()
        data = [(str(row[0]), str(row[1])) for row in rows]
        print(f"Data sample: {data[:5] if data else 'No data'}")
        print(f"Data length: {len(data)}")
        df = pd.DataFrame(data, columns=["invoice_number", "item_name"])
        basket = pd.crosstab(index=df['invoice_number'], columns=df['item_name']).astype(bool)
        frequent_itemsets = apriori(basket, min_support=0.01, use_colnames=True)
        if frequent_itemsets.empty:
            return jsonify({
                "success": False,
                "message": "No frequent itemsets found. Try lowering the support threshold.",
                "data_sample": df.head(10).to_dict('records')
            }), 200
        rules = association_rules(frequent_itemsets, metric="lift", min_threshold=1.0)
        if rules.empty:
            return jsonify({
                "success": False,
                "message": "No association rules found. Try lowering the lift threshold.",
                "itemsets_found": len(frequent_itemsets)
            }), 200
        rules = rules.replace([float('inf'), float('-inf')], 999.99)
        results = []
        for _, row in rules.iterrows():
            results.append({
                'antecedents': list(row['antecedents']),
                'consequents': list(row['consequents']),
                'support': float(row['support']),
                'confidence': float(row['confidence']),
                'lift': float(row['lift'])
            })
        return jsonify({
            "success": True,
            "rules_count": len(results),
            "rules": results[:20]
        })
    except Exception as e:
        print("Error:", str(e))
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/recommend/<item_id>', methods=['GET'])
def recommend_item(item_id):
    try:
        print(f"Received recommendation request for item_id: {item_id}")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT invoice_number, diffitemname FROM invoice_itemized")
        rows = cursor.fetchall()
        conn.close()
        data = [(str(row[0]), str(row[1])) for row in rows]
        print(f"Data sample for recommendation: {data[:5] if data else 'No data'}")
        print(f"Data length: {len(data)}")
        df = pd.DataFrame(data, columns=["invoice_number", "item_name"])
        basket = pd.crosstab(index=df['invoice_number'], columns=df['item_name']).astype(bool)
        frequent_itemsets = apriori(basket, min_support=0.01, use_colnames=True)
        if frequent_itemsets.empty:
            result = {
                "success": False,
                "message": "No frequent itemsets found. Try lowering the support threshold.",
                "item_id": item_id
            }
            return Response(json.dumps(result), mimetype='application/json')
        rules = association_rules(frequent_itemsets, metric="lift", min_threshold=1.0)
        if rules.empty:
            result = {
                "success": False,
                "message": "No association rules found. Try lowering the lift threshold.",
                "item_id": item_id
            }
            return Response(json.dumps(result), mimetype='application/json')
        rules = rules.replace([float('inf'), float('-inf')], 999.99)
        recommendations = []
        for _, row in rules.iterrows():
            antecedents = list(row['antecedents'])
            if item_id in antecedents:
                for item in list(row['consequents']):
                    recommendations.append({
                        "item": item,
                        "confidence": float(row['confidence']),
                        "lift": float(row['lift'])
                    })
        recommendations.sort(key=lambda x: x["lift"], reverse=True)
        recommendations = recommendations[:5]
        result = {
            "success": True,
            "item_id": item_id,
            "recommendations": recommendations
        }
        response = Response(json.dumps(result, default=str), mimetype='application/json')
        response.headers['Content-Type'] = 'application/json'
        return response
    except Exception as e:
        print("Error:", str(e))
        import traceback
        traceback.print_exc()
        error_result = {"error": str(e), "success": False, "item_id": item_id}
        response = Response(json.dumps(error_result), mimetype='application/json', status=500)
        response.headers['Content-Type'] = 'application/json'
        return response

# ------------------------------------------------------------------------------
# Inventory Dashboard API
# ------------------------------------------------------------------------------
@app.route('/api/inventory_dashboard', methods=['GET'])
def get_inventory_dashboard():
    """
    Provides comprehensive inventory metrics and insights.
    """
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        department = request.args.get('department')
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else datetime.now() - timedelta(days=720)
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else datetime.now()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            inventory_query = """
                SELECT 
                    COUNT(*) as total_items,
                    SUM(In_Stock) as total_stock,
                    SUM(Cost * In_Stock) as total_inventory_cost,
                    SUM(Price * In_Stock) as total_inventory_value,
                    AVG(In_Stock) as avg_stock_per_item,
                    SUM(CASE WHEN In_Stock <= Reorder_Level THEN 1 ELSE 0 END) as items_to_reorder,
                    SUM(CASE WHEN In_Stock = 0 THEN 1 ELSE 0 END) as out_of_stock_items
                FROM Inventory
            """
            if department:
                inventory_query += " WHERE Dept_ID = ?"
                cursor.execute(inventory_query, (department,))
            else:
                cursor.execute(inventory_query)
            inventory_summary = cursor.fetchone()
            dept_query = """
                SELECT 
                    Dept_ID,
                    COUNT(*) as item_count,
                    SUM(In_Stock) as total_stock,
                    SUM(Cost * In_Stock) as inventory_cost,
                    SUM(Price * In_Stock) as inventory_value,
                    SUM(CASE WHEN In_Stock <= Reorder_Level THEN 1 ELSE 0 END) as items_to_reorder
                FROM Inventory
                WHERE Dept_ID IS NOT NULL AND Dept_ID != 'NONE'
                GROUP BY Dept_ID
                ORDER BY inventory_value DESC
            """
            cursor.execute(dept_query)
            dept_rows = cursor.fetchall()
            departments = []
            for row in dept_rows:
                departments.append({
                    'department': row[0],
                    'item_count': row[1],
                    'total_stock': row[2],
                    'inventory_cost': float(row[3]) if row[3] else 0,
                    'inventory_value': float(row[4]) if row[4] else 0,
                    'items_to_reorder': row[5]
                })
            if department:
                top_selling_query = """
                    SELECT TOP 20
                        i.ItemNum,
                        i.ItemName,
                        SUM(ii.Quantity) as total_quantity_sold,
                        COUNT(DISTINCT ii.Invoice_Number) as order_count,
                        i.In_Stock as current_stock,
                        i.Price as unit_price,
                        i.Cost as unit_cost,
                        SUM(ii.Quantity * ii.PricePer) as total_revenue,
                        SUM(ii.Quantity * i.Cost) as total_cost
                    FROM Invoice_Itemized ii
                    JOIN Inventory i ON ii.ItemNum = i.ItemNum
                    JOIN Invoice_Totals it ON ii.Invoice_Number = it.Invoice_Number
                    WHERE it.DateTime BETWEEN ? AND ? AND i.Dept_ID = ?
                    GROUP BY i.ItemNum, i.ItemName, i.In_Stock, i.Price, i.Cost 
                    ORDER BY total_quantity_sold DESC
                """
                cursor.execute(top_selling_query, (start_date, end_date, department))
            else:
                top_selling_query = """
                    SELECT TOP 20
                        i.ItemNum,
                        i.ItemName,
                        SUM(ii.Quantity) as total_quantity_sold,
                        COUNT(DISTINCT ii.Invoice_Number) as order_count,
                        i.In_Stock as current_stock,
                        i.Price as unit_price,
                        i.Cost as unit_cost,
                        SUM(ii.Quantity * ii.PricePer) as total_revenue,
                        SUM(ii.Quantity * i.Cost) as total_cost
                    FROM Invoice_Itemized ii
                    JOIN Inventory i ON ii.ItemNum = i.ItemNum
                    JOIN Invoice_Totals it ON ii.Invoice_Number = it.Invoice_Number
                    WHERE it.DateTime BETWEEN ? AND ?
                    GROUP BY i.ItemNum, i.ItemName, i.In_Stock, i.Price, i.Cost 
                    ORDER BY total_quantity_sold DESC
                """
                cursor.execute(top_selling_query, (start_date, end_date))
            top_selling_rows = cursor.fetchall()
            top_selling_items = []
            for row in top_selling_rows:
                total_revenue = float(row[7]) if row[7] else 0
                total_cost = float(row[8]) if row[8] else 0
                profit = total_revenue - total_cost
                profit_margin = (profit / total_revenue * 100) if total_revenue > 0 else 0
                top_selling_items.append({
                    'item_num': row[0],
                    'item_name': row[1],
                    'quantity_sold': row[2],
                    'order_count': row[3],
                    'current_stock': row[4],
                    'unit_price': float(row[5]) if row[5] else 0,
                    'unit_cost': float(row[6]) if row[6] else 0,
                    'total_revenue': total_revenue,
                    'total_cost': total_cost,
                    'profit': profit,
                    'profit_margin': profit_margin
                })
            reorder_query = """
                SELECT 
                    ItemNum,
                    ItemName,
                    In_Stock,
                    Reorder_Level,
                    Reorder_Quantity,
                    Cost,
                    Price,
                    Dept_ID,
                    (Reorder_Level - In_Stock) as shortage
                FROM Inventory
                WHERE In_Stock <= Reorder_Level
            """
            if department:
                reorder_query += " AND Dept_ID = ? ORDER BY shortage DESC"
                cursor.execute(reorder_query, (department,))
            else:
                reorder_query += " ORDER BY shortage DESC"
                cursor.execute(reorder_query)
            reorder_rows = cursor.fetchall()
            items_to_reorder = []
            for row in reorder_rows:
                items_to_reorder.append({
                    'item_num': row[0],
                    'item_name': row[1],
                    'current_stock': row[2],
                    'reorder_level': row[3],
                    'reorder_quantity': row[4],
                    'unit_cost': float(row[5]) if row[5] else 0,
                    'unit_price': float(row[6]) if row[6] else 0,
                    'department': row[7],
                    'shortage': row[8]
                })
            turnover_query = """
                SELECT 
                    inv.Dept_ID,
                    SUM(ii.Quantity) as total_sold,
                    AVG(inv.In_Stock) as avg_inventory,
                    CASE WHEN AVG(inv.In_Stock) > 0 THEN SUM(ii.Quantity) / AVG(inv.In_Stock) ELSE 0 END as turnover_ratio
                FROM Invoice_Itemized ii
                JOIN Inventory inv ON ii.ItemNum = inv.ItemNum
                JOIN Invoice_Totals it ON ii.Invoice_Number = it.Invoice_Number
                WHERE it.DateTime BETWEEN ? AND ?
                GROUP BY inv.Dept_ID
                ORDER BY turnover_ratio DESC
            """
            cursor.execute(turnover_query, (start_date, end_date))
            turnover_rows = cursor.fetchall()
            inventory_turnover = []
            for row in turnover_rows:
                inventory_turnover.append({
                    'department': row[0],
                    'total_sold': row[1],
                    'avg_inventory': float(row[2]) if row[2] else 0,
                    'turnover_ratio': float(row[3]) if row[3] else 0
                })
            trend_query = """
                SELECT 
                    CAST(it.DateTime AS DATE) as sale_date,
                    COUNT(DISTINCT it.Invoice_Number) as order_count,
                    SUM(it.Total_Price) as total_sales,
                    COUNT(DISTINCT ii.ItemNum) as unique_items_sold,
                    SUM(ii.Quantity) as total_quantity_sold
                FROM Invoice_Totals it
                JOIN Invoice_Itemized ii ON it.Invoice_Number = ii.Invoice_Number
                WHERE it.DateTime BETWEEN ? AND ?
                GROUP BY CAST(it.DateTime AS DATE)
                ORDER BY sale_date
            """
            cursor.execute(trend_query, (start_date, end_date))
            trend_rows = cursor.fetchall()
            sales_trend = []
            for row in trend_rows:
                sales_trend.append({
                    'date': row[0].isoformat() if row[0] else None,
                    'order_count': row[1],
                    'total_sales': float(row[2]) if row[2] else 0,
                    'unique_items_sold': row[3],
                    'total_quantity_sold': row[4]
                })
            dashboard_data = {
                'inventory_summary': {
                    'total_items': inventory_summary[0],
                    'total_stock': inventory_summary[1],
                    'total_inventory_cost': float(inventory_summary[2]) if inventory_summary[2] else 0,
                    'total_inventory_value': float(inventory_summary[3]) if inventory_summary[3] else 0,
                    'avg_stock_per_item': float(inventory_summary[4]) if inventory_summary[4] else 0,
                    'items_to_reorder': inventory_summary[5],
                    'out_of_stock_items': inventory_summary[6]
                },
                'departments': departments,
                'top_selling_items': top_selling_items,
                'items_to_reorder': items_to_reorder,
                'inventory_turnover': inventory_turnover,
                'sales_trend': sales_trend,
                'filters': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'department': department
                }
            }
            return jsonify(dashboard_data), 200
    except Exception as e:
        print(f"Error in inventory dashboard: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/insert_data', methods=['POST'])
def insert_data():
    data = request.get_json()

    try:
        # Extract required fields using direct indexing.
        ItemNum = data["ItemNum"]
        ItemName = data["ItemName"]
        Cost = data["Cost"]
        Price = data["Price"]
        
        # For Dept_ID, use the provided value or a default that should exist.
        # Ensure the default value ("DEFAULT_DEPT") exists in your Departments table.
        Dept_ID = data["Dept_ID"] if "Dept_ID" in data else "DEFAULT_DEPT"
    except KeyError as e:
        missing_field = e.args[0]
        return jsonify({"error": f"Missing required field: {missing_field}"}), 400

    # Establish the database connection.
    connection = get_db_connection()
    cursor = connection.cursor()

    # Validate that the provided Dept_ID exists in the Departments table.
    cursor.execute("SELECT Dept_ID FROM Departments WHERE Dept_ID = ?", (Dept_ID,))
    if cursor.fetchone() is None:
        cursor.close()
        connection.close()
        return jsonify({"error": "Invalid Dept_ID: department does not exist."}), 400

    # Prepare the queries and parameters as before.
    inventory_query = """
        INSERT INTO Inventory (
            ItemNum, ItemName, Store_ID, Cost,           -- 1-4
            Price, Retail_Price, In_Stock, Reorder_Level,  -- 5-8
            Reorder_Quantity, Tax_1, Tax_2, Tax_3,         -- 9-12
            Vendor_Number, Dept_ID, IsKit, IsModifier,     -- 13-16
            Kit_Override, Inv_Num_Barcode_Labels, Use_Serial_Numbers, Num_Bonus_Points,  -- 17-20
            IsRental, Use_Bulk_Pricing, Print_Ticket, Print_Voucher,  -- 21-24
            Num_Days_Valid, IsMatrixItem, Vendor_Part_Num, Location, -- 25-28
            AutoWeigh, numBoxes, Dirty, Tear,             -- 29-32
            NumPerCase, FoodStampable, ReOrder_Cost, Helper_ItemNum,  -- 33-36
            ItemName_Extra, Exclude_Acct_Limit, Check_ID, Old_InStock,  -- 37-40
            Date_Created, ItemType, Prompt_Price, Prompt_Quantity, -- 41-44
            Inactive, Allow_BuyBack, Last_Sold, Unit_Type,  -- 45-48
            Unit_Size, Fixed_Tax, DOB, Special_Permission,  -- 49-52
            Prompt_Description, Check_ID2, Count_This_Item, Transfer_Cost_Markup,  -- 53-56
            Print_On_Receipt, Transfer_Markup_Enabled, As_Is, InStock_Committed, -- 57-60
            RequireCustomer, PromptCompletionDate, PromptInvoiceNotes, Prompt_DescriptionOverDollarAmt,  -- 61-64
            Exclude_From_Loyalty, BarTaxInclusive, ScaleSingleDeduct, GLNumber, -- 65-68
            ModifierType, Position, numberOfFreeToppings, ScaleItemType,  -- 69-72
            DiscountType, AllowReturns, SuggestedDeposit, Liability,  -- 73-76
            IsDeleted, ItemLocale, QuantityRequired, AllowOnDepositInvoices,  -- 77-80
            Import_Markup, PricePerMeasure, UnitMeasure, ShipCompliantProductType, -- 81-84
            AlcoholContent, AvailableOnline, AllowOnFleetCard, DoughnutTax,  -- 85-88
            DisplayTaxInPrice, NeverPrintInKitchen, Tax_4, Tax_5,  -- 89-92
            Tax_6, DisableInventoryUpload, InvoiceLimitQty, ItemCategory,  -- 93-96
            IsRestrictedPerInvoice, TagStatus              -- 97-98
        ) VALUES (
            ?, ?, ?, ?,                             -- 1-4
            ?, ?, ?, ?,                             -- 5-8
            ?, ?, ?, ?,                             -- 9-12
            ?, ?, ?, ?,                             -- 13-16
            ?, ?, ?, ?,                             -- 17-20
            ?, ?, ?, ?,                             -- 21-24
            ?, ?, ?, ?,                             -- 25-28
            ?, ?, ?, ?,                             -- 29-32
            ?, ?, ?, ?,                             -- 33-36
            ?, ?, ?, ?,                             -- 37-40
            ?, ?, ?, ?,                             -- 41-44
            ?, ?, ?, ?,                             -- 45-48
            ?, ?, ?, ?,                             -- 49-52
            ?, ?, ?, ?,                             -- 53-56
            ?, ?, ?, ?,                             -- 57-60
            ?, ?, ?, ?,                             -- 61-64
            ?, ?, ?, ?,                             -- 65-68
            ?, ?, ?, ?,                             -- 69-72
            ?, ?, ?, ?,                             -- 73-76
            ?, ?, ?, ?,                             -- 77-80
            ?, ?, ?, ?,                             -- 81-84
            ?, ?, ?, ?,                             -- 85-88
            ?, ?, ?, ?,                             -- 89-92
            ?, ?, ?, ?,                             -- 93-96
            ?, ?                                    -- 97-98
        )
    """
    inventory_params = [
        ItemNum, ItemName, 1001, Cost,            # 1-4
        Price, 0.00, 0.00, 0,                       # 5-8
        0, 0, 0, 0,                               # 9-12
        None, Dept_ID, 0, 0,                        # 13-16
        0.00, 0, 0, 0,                             # 17-20
        0, 0, 0, 0,                                # 21-24
        0, 0, 0, 0,                                # 25-28
        0, 0, 0, 0,                                # 29-32
        0, 0, 0, 0,                                # 33-36
        1, 0, 0, 0,                                # 37-40
        data["Date_Created"], data["ItemType"], data["Prompt_Price"], data["Prompt_Quantity"],  # 41-44
        0, 0, None, 'UOM',                          # 45-48
        None, 0, None, 0,                           # 49-52
        0, 0, 0, 0,                                # 53-56
        0, 0, 0, 0,                                # 57-60
        0, None, None, 0,                           # 61-64
        0, 0, 0, None,                             # 65-68
        None, None, 0, None,                        # 69-72
        0, 0, 0, 0,                                # 73-76
        0, None, 0, 0,                             # 77-80
        0, 0, None, None,                          # 81-84
        0, 0, 0, 0,                                # 85-88
        0, 0, 0, 0,                                # 89-92
        0, 0, 0, 0,                                # 93-96
        0, None                                   # 97-98
    ]

    # Build queries and parameters for additional tables (kit_index, Inventory_Onsale_Info)
    kit_query = """
        INSERT INTO kit_index (
            Kit_ID, Store_ID, ItemNum, Discount, Quantity, [Index], Price, Description, InvoiceMethodToUse, ChoiceLockdown
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """
    kit_params = [
        data["Kit_ID"], data["Store_ID"], ItemNum,
        0, 0, 0, 0, '', 0, 0
    ]

    onsale_query = """
        INSERT INTO Inventory_Onsale_Info (
            ItemNum, Store_ID, Sale_Start, Sale_End, [Percent], Price, SalePriceType
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?
        )
    """
    onsale_params = [
        ItemNum, data["Store_ID"],
        data["Sale_Start"], data["Sale_End"],
        0, 0, 0
    ]

    try:
        # Execute the three insertions.
        cursor.execute(inventory_query, inventory_params)
        cursor.execute(kit_query, kit_params)
        cursor.execute(onsale_query, onsale_params)
        connection.commit()
        return jsonify({"message": "Data inserted successfully."}), 201
    except pyodbc.Error as e:
        error_message = str(e)
        print(f"Database error: {error_message}")
        return jsonify({"error": "Database error", "details": error_message}), 500
    finally:
        cursor.close()
        connection.close()



@app.route('/insert_basic_item', methods=['POST'])
def insert_basic_item():
    data = request.get_json()

    try:
        # Extract required fields
        Kit_ID    = data["Kit_ID"]
        ItemName  = data["ItemName"]
        Price     = float(data["Price"])
        Quantity  = int(data["Quantity"])
        Sale_Start = data["Sale_Start"]
        Sale_End   = data["Sale_End"]
    except KeyError as e:
        missing_field = e.args[0]
        return jsonify({"error": f"Missing required field: {missing_field}"}), 400
    except ValueError as e:
        return jsonify({"error": "Invalid data type", "details": str(e)}), 400

    # Generate a unique ItemNum (using the current timestamp)
    ItemNum = int(time.time() * 1000)
    
    # Default values for fields not provided by the client
    Cost = 0.0
    Dept_ID = "NONE"
    Store_ID = 1001
    Date_Created = datetime.now().strftime("%Y-%m-%d")
    ItemType = 5
    Prompt_Price = 0.0
    Prompt_Quantity = 0

    # Establish the database connection.
    connection = get_db_connection()
    cursor = connection.cursor()

    # Validate that the default Dept_ID exists in the Departments table.
    cursor.execute("SELECT Dept_ID FROM Departments WHERE Dept_ID = ?", (Dept_ID,))
    if cursor.fetchone() is None:
        cursor.close()
        connection.close()
        return jsonify({"error": "Invalid Dept_ID: department does not exist."}), 400

    # Prepare the Inventory insertion query.
    inventory_query = """
        INSERT INTO Inventory (
            ItemNum, ItemName, Store_ID, Cost,           
            Price, Retail_Price, In_Stock, Reorder_Level,  
            Reorder_Quantity, Tax_1, Tax_2, Tax_3,         
            Vendor_Number, Dept_ID, IsKit, IsModifier,     
            Kit_Override, Inv_Num_Barcode_Labels, Use_Serial_Numbers, Num_Bonus_Points,  
            IsRental, Use_Bulk_Pricing, Print_Ticket, Print_Voucher,  
            Num_Days_Valid, IsMatrixItem, Vendor_Part_Num, Location, 
            AutoWeigh, numBoxes, Dirty, Tear,             
            NumPerCase, FoodStampable, ReOrder_Cost, Helper_ItemNum,  
            ItemName_Extra, Exclude_Acct_Limit, Check_ID, Old_InStock,  
            Date_Created, ItemType, Prompt_Price, Prompt_Quantity, 
            Inactive, Allow_BuyBack, Last_Sold, Unit_Type,  
            Unit_Size, Fixed_Tax, DOB, Special_Permission,  
            Prompt_Description, Check_ID2, Count_This_Item, Transfer_Cost_Markup,  
            Print_On_Receipt, Transfer_Markup_Enabled, As_Is, InStock_Committed, 
            RequireCustomer, PromptCompletionDate, PromptInvoiceNotes, Prompt_DescriptionOverDollarAmt,  
            Exclude_From_Loyalty, BarTaxInclusive, ScaleSingleDeduct, GLNumber, 
            ModifierType, Position, numberOfFreeToppings, ScaleItemType,  
            DiscountType, AllowReturns, SuggestedDeposit, Liability,  
            IsDeleted, ItemLocale, QuantityRequired, AllowOnDepositInvoices,  
            Import_Markup, PricePerMeasure, UnitMeasure, ShipCompliantProductType, 
            AlcoholContent, AvailableOnline, AllowOnFleetCard, DoughnutTax,  
            DisplayTaxInPrice, NeverPrintInKitchen, Tax_4, Tax_5,  
            Tax_6, DisableInventoryUpload, InvoiceLimitQty, ItemCategory,  
            IsRestrictedPerInvoice, TagStatus              
        ) VALUES (
             ?, ?, ?, ?,                             -- 1-4
            ?, ?, ?, ?,                             -- 5-8
            ?, ?, ?, ?,                             -- 9-12
            ?, ?, ?, ?,                             -- 13-16
            ?, ?, ?, ?,                             -- 17-20
            ?, ?, ?, ?,                             -- 21-24
            ?, ?, ?, ?,                             -- 25-28
            ?, ?, ?, ?,                             -- 29-32
            ?, ?, ?, ?,                             -- 33-36
            ?, ?, ?, ?,                             -- 37-40
            ?, ?, ?, ?,                             -- 41-44
            ?, ?, ?, ?,                             -- 45-48
            ?, ?, ?, ?,                             -- 49-52
            ?, ?, ?, ?,                             -- 53-56
            ?, ?, ?, ?,                             -- 57-60
            ?, ?, ?, ?,                             -- 61-64
            ?, ?, ?, ?,                             -- 65-68
            ?, ?, ?, ?,                             -- 69-72
            ?, ?, ?, ?,                             -- 73-76
            ?, ?, ?, ?,                             -- 77-80
            ?, ?, ?, ?,                             -- 81-84
            ?, ?, ?, ?,                             -- 85-88
            ?, ?, ?, ?,                             -- 89-92
            ?, ?, ?, ?,                             -- 93-96
            ?, ?                                    -- 97-98                        
        )
    """
    inventory_params = [
        ItemNum, ItemName, Store_ID, Cost,                      # 1-4
        Price, 0.00, Quantity, 0,                               # 5-8
        0, 0, 0, 0,                                           # 9-12
        None, Dept_ID, 1, 0,                                  # 13-16 (Assume IsKit = 1)
        0.00, 0, 0, 0,                                       # 17-20
        0, 0, 0, 0,                                          # 21-24
        0, 0, 0, 0,                                          # 25-28
        0, 0, 0, 0,                                          # 29-32
        0, 0, 0, 0,                                          # 33-36
        1, 0, 0, 0,                                          # 37-40 (Assume ItemName_Extra = 1)
        Date_Created, ItemType, Prompt_Price, Prompt_Quantity, # 41-44
        0, 0, None, 'UOM',                                    # 45-48
        None, 0, None, 0,                                     # 49-52
        0, 0, 0, 0,                                          # 53-56
        0, 0, 0, 0,                                          # 57-60
        0, None, None, 0,                                     # 61-64
        0, 0, 0, None,                                       # 65-68
        None, None, 0, None,                                  # 69-72
        0, 0, 0, 0,                                          # 73-76
        0, None, 0, 0,                                       # 77-80
        0, 0, None, None,                                    # 81-84
        0, 0, 0, 0,                                          # 85-88
        0, 0, 0, 0,                                          # 89-92
        0, 0, 0, 0,                                          # 93-96
        0, None                                             # 97-98
    ]

    # Prepare the kit_index insertion query.
    kit_query = """
        INSERT INTO kit_index (
            Kit_ID, Store_ID, ItemNum, Discount, Quantity, [Index], Price, Description, InvoiceMethodToUse, ChoiceLockdown
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """
    kit_params = [
        Kit_ID, Store_ID, ItemNum,
        0, Quantity, 0, Price, '', 0, 0
    ]

    # Prepare the Inventory_Onsale_Info insertion query.
    onsale_query = """
        INSERT INTO Inventory_Onsale_Info (
            ItemNum, Store_ID, Sale_Start, Sale_End, [Percent], Price, SalePriceType
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?
        )
    """
    onsale_params = [
        ItemNum, Store_ID,
        Sale_Start, Sale_End,
        0, Price, 0
    ]
    try:
        cursor.execute(inventory_query, inventory_params)
        cursor.execute(kit_query, kit_params)
        cursor.execute(onsale_query, onsale_params)
        connection.commit()
        return jsonify({"message": "Data inserted successfully."}), 201
    except pyodbc.Error as e:
        error_message = str(e)
        print(f"Database error: {error_message}")
        return jsonify({"error": "Database error", "details": error_message}), 500
    finally:
        cursor.close()
        connection.close()


# ------------------------------------------------------------------------------
# Fetch CSV file 
# ------------------------------------------------------------------------------

@app.route('/api/csv_data', methods=['GET'])
def get_csv_data():
    # 1. Load your CSV file
    # If your file is named differently or in another folder, adjust the path below
    csv_file_path = 'cleaned_data.csv' 
    df = pd.read_csv(csv_file_path)

    # 2. Convert the DataFrame to a list of dictionaries
    # orient='records' => List of row objects
    data_list = df.to_dict(orient='records')

    # 3. Return JSON to the client
    return jsonify(data_list)


# ------------------------------------------------------------------------------
# Precess the CSV File
# ------------------------------------------------------------------------------
@app.route('/api/processed_data', methods=['GET'])
def get_processed_data():
    """
    NEW route:
    1. Pulls data from /api/csv_data,
    2. Extracts 'Quantity' from 'Companion item' with a regex,
    3. Trims 'ItemName' at the first newline (if one exists),
    4. Returns the enhanced JSON.
    """
    # 1) Retrieve data from the existing endpoint
    response = requests.get('http://localhost:5000/api/csv_data')
    raw_data = response.json()  # Parse the JSON into a list of dictionaries

    # 2) Convert the list of dictionaries to a DataFrame
    df = pd.DataFrame(raw_data)

    # 3) Extract quantity from the "Companion item" field
    #    e.g., find integers inside parentheses like (1), (5), etc.
    pattern = re.compile(r'\((\d+)\)')

    def extract_quantity(text):
        if pd.isna(text):
            return None
        match = pattern.search(str(text))
        if match:
            return int(match.group(1))
        return None

    df['Quantity'] = df['Companion item'].apply(extract_quantity)

    # 4) Trim the "ItemName" so that it only includes text before the first newline.
    #    This function now converts any input into a string and only splits if a newline exists.
    def trim_item(value):
        if pd.isna(value):
            return ""  # Return an empty string if the value is missing
        try:
            text = str(value)
        except Exception:
            text = ""
        # Split by newline if present; otherwise return the complete string.
        return text.split('\n')[0]

    df['ItemName'] = df['ItemName'].apply(trim_item)

    # 5) Convert the DataFrame back to JSON (list of dicts) and return it in the response.
    processed_data = df.to_dict(orient='records')
    return jsonify(processed_data)



# ------------------------------------------------------------------------------
# Function to Trim Itemname 
# ------------------------------------------------------------------------------
def safe_trim_item(value, max_length=30):
    """Converts any input to a string and returns only the first max_length characters."""
    if value is None:
        return "Unknown"
    try:
        text = str(value)
    except Exception:
        return "Unknown"
    # Trim at the first newline and then slice the string to ensure it is at most max_length
    trimmed = text.split('\n')[0]
    return trimmed[:max_length]

# ------------------------------------------------------------------------------
# Insert Items from Processed API
# ------------------------------------------------------------------------------

@app.route('/insert_items_from_processed_data', methods=['GET'])
def insert_items_from_processed_data():
    """
    This route:
      1. Fetches the processed data from /api/processed_data,
      2. Iterates over each record,
      3. Inserts data into the DB using fields from your JSON.
    """
    # Define the maximum allowed length for ItemName (adjust based on your schema)
    ITEM_NAME_MAX_LENGTH = 50

    # Helper function to safely process the ItemName field.
    def safe_trim_item(value, max_length=ITEM_NAME_MAX_LENGTH):
        """Converts any input to a string, trims at the first newline, and truncates to max_length."""
        if value is None:
            return "Unknown"
        try:
            text = str(value)
        except Exception:
            text = "Unknown"
        # Return only the text before the first newline.
        trimmed = text.split('\n')[0]
        # Truncate the string if it's longer than max_length.
        if len(trimmed) > max_length:
            return trimmed[:max_length]
        return trimmed

    # 1) Fetch from /api/processed_data
    response = requests.get('http://localhost:5000/api/processed_data')
    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch /api/processed_data"}), 500

    processed_items = response.json()

    connection = get_db_connection()
    cursor = connection.cursor()

    success_count = 0
    fail_count = 0

    for record in processed_items:
        Kit_ID = record.get("Kit_ID", "DefaultKitID")
        # Process ItemName to get only the first 30 characters if it's too long.
        ItemName = safe_trim_item(record.get("ItemName", "Unknown"), 30)
        
        try:
            Price = float(record.get("Price", 0.0))
        except Exception:
            Price = 0.0

        try:
            Quantity = int(record.get("Quantity", 0))
        except Exception:
            Quantity = 0

        Sale_Start = record.get("Sale_Start", "2025-01-01")
        Sale_End = record.get("Sale_end", "2025-12-31")
        
        ItemNum = int(time.time() * 1000)
        Cost = 0.0
        Dept_ID = "NONE"   # Ensure this exists in the Departments table
        Store_ID = 1001
        Date_Created = datetime.now().strftime("%Y-%m-%d")
        ItemType = 5
        Prompt_Price = 0.0
        Prompt_Quantity = 0
        IsKit = 1
        IsModifier = 0
        VendorNum = None

        # Build your query and parameters as before, using the truncated ItemName.
        inventory_query = """
            INSERT INTO Inventory (
                ItemNum, ItemName, Store_ID, Cost,           
                Price, Retail_Price, In_Stock, Reorder_Level,  
                Reorder_Quantity, Tax_1, Tax_2, Tax_3,         
                Vendor_Number, Dept_ID, IsKit, IsModifier,     
                Kit_Override, Inv_Num_Barcode_Labels, Use_Serial_Numbers, Num_Bonus_Points,  
                IsRental, Use_Bulk_Pricing, Print_Ticket, Print_Voucher,  
                Num_Days_Valid, IsMatrixItem, Vendor_Part_Num, Location, 
                AutoWeigh, numBoxes, Dirty, Tear,             
                NumPerCase, FoodStampable, ReOrder_Cost, Helper_ItemNum,  
                ItemName_Extra, Exclude_Acct_Limit, Check_ID, Old_InStock,  
                Date_Created, ItemType, Prompt_Price, Prompt_Quantity, 
                Inactive, Allow_BuyBack, Last_Sold, Unit_Type,  
                Unit_Size, Fixed_Tax, DOB, Special_Permission,  
                Prompt_Description, Check_ID2, Count_This_Item, Transfer_Cost_Markup,  
                Print_On_Receipt, Transfer_Markup_Enabled, As_Is, InStock_Committed, 
                RequireCustomer, PromptCompletionDate, PromptInvoiceNotes, Prompt_DescriptionOverDollarAmt,  
                Exclude_From_Loyalty, BarTaxInclusive, ScaleSingleDeduct, GLNumber, 
                ModifierType, Position, numberOfFreeToppings, ScaleItemType,  
                DiscountType, AllowReturns, SuggestedDeposit, Liability,  
                IsDeleted, ItemLocale, QuantityRequired, AllowOnDepositInvoices,  
                Import_Markup, PricePerMeasure, UnitMeasure, ShipCompliantProductType, 
                AlcoholContent, AvailableOnline, AllowOnFleetCard, DoughnutTax,  
                DisplayTaxInPrice, NeverPrintInKitchen, Tax_4, Tax_5,  
                Tax_6, DisableInventoryUpload, InvoiceLimitQty, ItemCategory,  
                IsRestrictedPerInvoice, TagStatus              
            ) VALUES (
                ?, ?, ?, ?,                             -- 1-4
                ?, ?, ?, ?,                             -- 5-8
                ?, ?, ?, ?,                             -- 9-12
                ?, ?, ?, ?,                             -- 13-16
                ?, ?, ?, ?,                             -- 17-20
                ?, ?, ?, ?,                             -- 21-24
                ?, ?, ?, ?,                             -- 25-28
                ?, ?, ?, ?,                             -- 29-32
                ?, ?, ?, ?,                             -- 33-36
                ?, ?, ?, ?,                             -- 37-40
                ?, ?, ?, ?,                             -- 41-44
                ?, ?, ?, ?,                             -- 45-48
                ?, ?, ?, ?,                             -- 49-52
                ?, ?, ?, ?,                             -- 53-56
                ?, ?, ?, ?,                             -- 57-60
                ?, ?, ?, ?,                             -- 61-64
                ?, ?, ?, ?,                             -- 65-68
                ?, ?, ?, ?,                             -- 69-72
                ?, ?, ?, ?,                             -- 73-76
                ?, ?, ?, ?,                             -- 77-80
                ?, ?, ?, ?,                             -- 81-84
                ?, ?, ?, ?,                             -- 85-88
                ?, ?, ?, ?,                             -- 89-92
                ?, ?, ?, ?,                             -- 93-96
                ?, ?                                    -- 97-98                        
            )
        """
        inventory_params = [
            ItemNum, ItemName, Store_ID, Cost,                      # 1-4
            Price, 0.00, Quantity, 0,                               # 5-8
            0, 0, 0, 0,                                           # 9-12
            None, Dept_ID, 1, 0,                                  # 13-16 (Assume IsKit = 1)
            0.00, 0, 0, 0,                                       # 17-20
            0, 0, 0, 0,                                          # 21-24
            0, 0, 0, 0,                                          # 25-28
            0, 0, 0, 0,                                          # 29-32
            0, 0, 0, 0,                                          # 33-36
            1, 0, 0, 0,                                          # 37-40 (Assume ItemName_Extra = 1)
            Date_Created, ItemType, Prompt_Price, Prompt_Quantity, # 41-44
            0, 0, None, 'UOM',                                    # 45-48
            None, 0, None, 0,                                     # 49-52
            0, 0, 0, 0,                                          # 53-56
            0, 0, 0, 0,                                          # 57-60
            0, None, None, 0,                                     # 61-64
            0, 0, 0, None,                                       # 65-68
            None, None, 0, None,                                  # 69-72
            0, 0, 0, 0,                                          # 73-76
            0, None, Quantity, 0,                                       # 77-80
            0, 0, None, None,                                    # 81-84
            0, 0, 0, 0,                                          # 85-88
            0, 0, 0, 0,                                          # 89-92
            0, 0, 0, 0,                                          # 93-96
            0, None                                             # 97-98
        ]

    # Then perform your other queries...

        # Prepare the kit_index insertion query.
        kit_query = """
            INSERT INTO kit_index (
                Kit_ID, Store_ID, ItemNum, Discount, Quantity, [Index], Price, Description, InvoiceMethodToUse, ChoiceLockdown
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """
        kit_params = [
            Kit_ID, Store_ID, ItemNum,
            0, Quantity, 0, Price, '', 0, 0
        ]

        # Prepare the Inventory_Onsale_Info insertion query.
        onsale_query = """
            INSERT INTO Inventory_Onsale_Info (
                ItemNum, Store_ID, Sale_Start, Sale_End, [Percent], Price, SalePriceType
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?
            )
        """
        onsale_params = [
            ItemNum, Store_ID, Sale_Start, Sale_End, 0, Price, 0
        ]

        try:
            # Validate that Dept_ID exists in the Departments table.
            cursor.execute("SELECT Dept_ID FROM Departments WHERE Dept_ID = ?", (Dept_ID,))
            if cursor.fetchone() is None:
                print(f"Invalid Dept_ID: {Dept_ID}. Skipping...")
                fail_count += 1
                continue

            cursor.execute(inventory_query, inventory_params)
            cursor.execute(kit_query, kit_params)
            cursor.execute(onsale_query, onsale_params)
            success_count += 1

        except pyodbc.Error as e:
            print(f"Database insertion error: {str(e)}")
            fail_count += 1

    # Commit all inserts at once
    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({
        "message": "Bulk insertion from /api/processed_data completed.",
        "success_count": success_count,
        "fail_count": fail_count
    })

def make_serializable(results):
    """Convert datetime and Decimal objects in the results to JSON serializable types."""
    processed_results = []
    for row in results:
        new_row = {}
        for key, value in row.items():
            if isinstance(value, (datetime, date)):
                new_row[key] = value.isoformat()
            elif isinstance(value, Decimal):
                new_row[key] = float(value)
            else:
                new_row[key] = value
        processed_results.append(new_row)
    return processed_results

@app.route('/api/receipt', methods=['GET'])
def receipt():
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        query = """
            SELECT 
                s.Company_Info_1,
                s.Company_Info_2,
                s.Company_Info_3,
                s.Company_Info_4,
                s.Company_Info_5,
                it.Invoice_Number, 
                ii.ItemNum,
                ii.DiffItemName,
                ii.Quantity,
                it.Store_ID, 
                it.Total_Price,
                (it.Total_Tax1 + it.Total_Tax2 + it.Total_Tax3) AS Tax,
                ct.SurChargeAmount,
                it.Grand_Total, 
                it.Amt_Tendered,
                it.Total_Cost,  
                it.DateTime,
                ct.Type,
                ct.Reference,
                ct.Approval,
                ct.tsi_Indicator,
                ct.type,
                ct.TruncatedCardNumber,
                ct.tc_acc,
                ct.emv_aid,
                emp.Cashier_ID,
                emp.First_Name
            FROM 
                invoice_totals AS it
            INNER JOIN 
                CC_Trans AS ct ON it.Invoice_Number = ct.CRENumber
            INNER JOIN 
                invoice_itemized AS ii ON it.Invoice_Number = ii.Invoice_Number
            INNER JOIN 
                employee AS emp ON it.cashier_id = emp.Cashier_ID
            INNER JOIN 
                setup AS s ON it.Store_ID = s.Store_ID
            ORDER BY 
                it.Invoice_Number DESC;
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        # Create a list of column names from cursor.description
        columns = [column[0] for column in cursor.description]
        # Convert each pyodbc.Row into a dictionary using the column names.
        results = [dict(zip(columns, row)) for row in rows]

        # Process the results to convert datetime/Decimal types.
        processed_results = make_serializable(results)
        return jsonify(processed_results)
    except Exception as e:
        print("Error executing query:", e)
        return jsonify({'error': 'Internal Server Error'}), 500
    finally:
        connection.close()

# ------------------------------------------------------------------------------
# Main Runner
# ------------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
