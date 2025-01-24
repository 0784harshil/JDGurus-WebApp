from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import pyodbc

app = Flask(__name__)
CORS(app)

# Define the connection string
server = 'HARSHIL\\PCAMERICA'  # Your server name
database = 'cresqlpridom'  # Your database name
connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;'

# Database connection configuration
def get_db_connection():
    conn = pyodbc.connect(connection_string)
    return conn

@app.route('/api/kit_details', methods=['GET'])
def get_kit_details():
    try:
        with pyodbc.connect(connection_string) as conn:
            cursor = conn.cursor()
            query = '''
            SELECT 
                ki.Kit_ID AS [PriceGroupID],
                inv.QuantityRequired AS [Quantity],
                inv.ItemName AS [Description],
                inv.Price AS [Bulk Price],
                (SELECT STUFF(
                     (SELECT ' | ' + CONVERT(VARCHAR, it.[DateTime], 120) 
                      FROM Invoice_Itemized int4
                      LEFT JOIN Kit_Index ki4 ON ki4.Kit_ID = int4.ItemNum
                      LEFT JOIN Invoice_Totals it ON it.Invoice_Number = int4.Invoice_Number
                      WHERE ki4.Kit_ID = ki.Kit_ID
                      FOR XML PATH('')), 1, 2, '')
                ) AS [Invoice Dates],
                (SELECT STUFF(
                     (SELECT ' | ' + CAST(int4.Invoice_Number AS VARCHAR) 
                      FROM Invoice_Itemized int4
                      LEFT JOIN Kit_Index ki4 ON ki4.Kit_ID = int4.ItemNum
                      WHERE ki4.Kit_ID = ki.Kit_ID 
                      FOR XML PATH('')), 1, 2, '')
                ) AS [Invoice_Number],
                (SELECT STUFF(
                     (SELECT ' | ' + ki2.ItemNum 
                      FROM Kit_Index ki2 
                      JOIN Inventory inv1 ON inv1.ItemNum = ki2.ItemNum
                      WHERE ki2.Kit_ID = ki.Kit_ID 
                      FOR XML PATH('')), 1, 2, '')
                ) AS [ItemNums],
                (SELECT STUFF(
                     (SELECT ' | ' + inv4.ItemName 
                      FROM Kit_Index ki2 
                      JOIN Inventory inv4 ON inv4.ItemNum = ki2.ItemNum
                      WHERE ki2.Kit_ID = ki.Kit_ID 
                      FOR XML PATH('')), 1, 2, '')
                ) AS [ItemNames],
                (SELECT STUFF(
                     (SELECT ' | ' + CAST(int1.PricePer AS VARCHAR) 
                      FROM Invoice_Itemized int1
                      LEFT JOIN Kit_Index ki3 ON ki3.Kit_ID = int1.ItemNum
                      WHERE ki3.Kit_ID = ki.Kit_ID 
                      FOR XML PATH('')), 1, 2, '')
                ) AS [Discount Amount]
            FROM 
                Kit_Index ki
            JOIN
                Inventory inv  
                ON inv.ItemNum = ki.Kit_ID
            '''
            cursor.execute(query)
            rows = cursor.fetchall()
            kit_details_list = []
            for row in rows:
                kit_details_list.append({
                    'PriceGroupID': row[0],
                    'Quantity': row[1],
                    'Description': row[2],
                    'Bulk Price': row[3],
                    'Invoice Dates': row[4],
                    'Invoice_Number': row[5],
                    'ItemNums': row[6],
                    'ItemNames': row[7],
                    'Discount Amount': row[8]
                })
            return jsonify(kit_details_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    


@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    try:
        with pyodbc.connect(connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Inventory")
            rows = cursor.fetchall()
            inventory_list = []
            for row in rows:
                inventory_list.append({
                    'id': row[0],
                    'name': row[1],
                    'quantity': row[2],
                    'price': row[3]
                })
            return jsonify(inventory_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/customers', methods=['GET'])
def get_customers():
    try:
        with pyodbc.connect(connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Customer")  # Assuming your customer table is named 'Customers'
            rows = cursor.fetchall()
            customer_list = []
            for row in rows:
                customer_list.append({
                    'id': row[0],  # Assuming the first column is ID
                    'name': row[1],  # Assuming the second column is Name
                    'email': row[2],  # Assuming the third column is Email
                    'phone': row[3]  # Assuming the fourth column is Phone
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
    
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    store_id = data.get('Store_ID')
    admin_password = data.get('Admin_Pass')

    try:
        with pyodbc.connect(connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM setup WHERE Store_ID = ? AND Admin_Pass = ?", (store_id, admin_password))
            user = cursor.fetchone()

            if user:
                return jsonify(success=True, message='Login successful!'), 200
            else:
                return jsonify(success=False, message='Invalid credentials'), 401
    except Exception as e:
        print(e)
        return jsonify(success=False, message='Server error'), 500


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

if __name__ == '__main__':
    app.run(debug=True)
