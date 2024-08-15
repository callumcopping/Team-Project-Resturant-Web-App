import datetime
from flask import Flask, jsonify, request, render_template, redirect, url_for, session  #Flask not being accessed MIGHT BE DEAD CODE.
from flask_sqlalchemy import SQLAlchemy
import database as db
import pydoc #not being accessed NEEDS TO BE REMOVED.
app = db.app
app.secret_key = 'hello this is our secret key'
#Secret key given to prevent error
class DatabaseConfig:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://1:1@43.143.17.85:3306/team33'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config.from_object(DatabaseConfig)
restaurant_db = db.restaurant_db
@app.route('/', methods=['GET', 'POST'])
def home():
    # clear session data when user first arrives to home page
    session.clear()
    error = None
    if request.method == 'POST':
        # retrieve the table_number input from the form data
        table_number = request.form['table_number']
        # check if the input is an integer
        if table_number.isdigit():
            # add the table to the database if it does not exist
            if not (db.Tables.query.get(table_number)):
                addTable(table_number)
            # redirect to customer page, with table number
            return redirect(url_for('customer', table_number=table_number))
        else:
            # set the error message if the input is not a valid integer
            error = 'Please enter a table number'
    # render the home template with the error message (if any)
    return render_template('home.html', error=error)
@app.route('/customer/<table_number>', methods=['GET', 'POST'])
def customer(table_number):
    # Check if order items are already in the session
    if 'order_items' not in session:
        session['order_items'] = {}
        session['tot_price'] = 0
    # Initialize menu_items outside the if statement
    menu_items = db.Menu.query.filter_by(available=True).all()
    if request.method == 'POST':
        # Check if the submit button was pressed
        if request.form.get('submit'):
            checkout(table_number)
        # Check if the needhelp button was pressed
        elif request.form.get('needhelp'):
            needhelp(table_number)
        elif request.form.get('checkpay'):
            success, message = checkpay(table_number)
            return render_template('customerMenu.html', table_number=table_number, order_items=session.get('order_items',{}), price = session.get('tot_price', 0), menu_items=menu_items, message=message)
        else:
            # Add new item to order
            try:
                menu_item = request.form['menu_item']
                # Construct the name of the quantity field
                quantity_field_name = f"{menu_item} quantity"
                quantity = int(request.form.get(quantity_field_name))
            except:
                # Handle errors when parsing form data
                return render_template('home.html', error="An error occured adding an item to your order sorry :(")
            # Update the order and total price
            order_items = session['order_items']
            if menu_item in order_items:
                order_items[menu_item] += quantity
            else:
                order_items[menu_item] = quantity
            session['order_items'] = order_items
            session['tot_price'] += fetch_price(menu_item) * quantity
            session['tot_price'] = round(session['tot_price'], 2)
    # Render the customer menu template with table number, order items and total price
    return render_template('customerMenu.html', table_number=table_number, order_items=session.get('order_items',{}), price = session.get('tot_price', 0), menu_items=menu_items)
def fetch_price(menu_item):
    # Fetch the price of the menu item from the database
    try:
        menu_item_db = db.Menu.query.filter_by(name=menu_item).first()
        item_price = float(menu_item_db.price)
        return item_price
    except:
        print("Error: Menu item ", {menu_item}, " not found in database.")
def fetch_item_id(menu_item):
    # Fetch the id of the menu item from the database
    try:
        menu_item_db = db.Menu.query.filter_by(name=menu_item).first()
        item_id = int(menu_item_db.item_id)
        return item_id
    except:
        print("Error: Menu item ", {menu_item}, " not found in database.")
def needhelp(table_number):
    # Use table_id to get need_help and change it to true if it is false.
    table = db.Tables.query.get(table_number)
    if table is None:
        print("Table Not Found")
    elif table.need_help == False:
        table.need_help  = True
    restaurant_db.session.commit()
def addTable(table_number):
    try:
        table = db.Tables(table_id=table_number)
        restaurant_db.session.add(table)
        restaurant_db.session.commit()
    except:
        print("error adding table")
@app.route('/waiter/<table_number>', methods=['GET', 'POST'])
def removehelpstatus(table_number):
    table = db.Tables.query.get(table_number)
    if table is None:
        print("Table Not Found")
    else:
        table.need_help  = False
        restaurant_db.session.commit()
    return waiter()
def checkpay(table_number):
    card_number = request.form['card_number']
    expiry_month = request.form['expiry_month'].zfill(2) #Deadcode not being accessed/used NEEDS TO BE REMOVED.
    paymenthistory = db.PaymentHistory(card_number=card_number,totalPrice=session['tot_price'],table_id=table_number)
    try:
        restaurant_db.session.add(paymenthistory)
        restaurant_db.session.commit()
        checkout(table_number)
        return True, "Payment Success :)"
    except:
        restaurant_db.session.rollback()
        return False, "Payment Failed, Wrong Card Number :("
def checkout(table_number):
    # Initialize variables to track the quantity of each menu item
    order_items = session['order_items']
    # get the current date and time
    time_of_order = datetime.datetime.now()
    # format the current date and time as it is stored in a mysql db
    time_of_order = time_of_order.strftime('%Y-%m-%d %H:%M:%S')
    # Create a new order with the table number and total price
    # Calculate the next order ID by counting the existing orders and adding 1
    next_order_id = db.Orders.query.count() + 1
    order = db.Orders(order_id=next_order_id,table_id=table_number, totalPrice=session['tot_price'], cooked=False, delivered=False, timeoforder=time_of_order, confirmed=False)
    try:
        restaurant_db.session.add(order)
        restaurant_db.session.commit()
    except:
        restaurant_db.session.rollback()
        # Use default id instead of calculated next order id
        order = db.Orders(table_id=table_number, totalPrice=session['tot_price'], cooked=False, delivered=False, timeoforder=time_of_order, confirmed=False)
        restaurant_db.session.add(order)
        restaurant_db.session.commit()
    try:
        # Add the items to the order
        for menu_item, quantity in order_items.items():
            item = db.Items(item_id=fetch_item_id(menu_item), order_id=order.order_id, quantity=quantity, price=fetch_price(menu_item)*quantity, ready=False)
            restaurant_db.session.add(item)
        restaurant_db.session.commit()
    except:
        print("Error adding items to db")
    # Pop session to clear customers cart
    session.pop('order_items', None)
    session.pop('tot_price', 0)
@app.route('/customer/<table_number>/delete/<item>/<qty>', methods=['GET', 'POST'])
def delete_item(table_number, item, qty):
    order_list = session['order_items']
    # Remove the specified item from the order list
    for i in range(int(qty)):
        if item in order_list:
            if order_list[item] > 1:
                order_list[item] -= 1
            else:
                order_list.pop(item)
    # Update the session variable with the updated order list
    session['order_items'] = order_list
    # Update currernt order price
    session['tot_price'] -= fetch_price(item) * int(qty)
    session['tot_price'] = round(session['tot_price'], 2)
    return redirect(url_for('customer', table_number=table_number))
def reset():
    # Delete all data in the database from tables 'items', 'orders' and 'tables'.
    restaurant_db.session.execute('DELETE FROM items')
    restaurant_db.session.execute('DELETE FROM orders')
    restaurant_db.session.execute('DELETE FROM tables')
    restaurant_db.session.commit()
@app.route('/waiter')
def waiter():
    #Now waiter page should only display items which are cooked.Before it displayed everything added to database.
    cooked_orders = db.Orders.query.filter_by(cooked=True, delivered=False, confirmed=True).order_by(db.Orders.timeoforder.asc()).all()
    uncooked_orders = db.Orders.query.filter_by(cooked=False, delivered=False, confirmed=False).order_by(db.Orders.timeoforder.asc()).all()
    tables = db.Tables.query.filter_by(need_help=True).all()
    #Code inspired from sqlalchemy documentation link:https://docs.sqlalchemy.org/en/14/orm/query.html
    return render_template ('waiter.html',cooked_orders=cooked_orders, uncooked_orders=uncooked_orders, tables=tables)
@app.route('/send_to_kitchen/<order_id>', methods=['GET', 'POST'])
def send_to_kitchen(order_id):
    order = db.Orders.query.get(order_id)
    items = db.Items.query.filter_by(order_id=order_id).all()
    for item in items:
        item.ready = False
    order.cooked = False
    restaurant_db.session.commit()
    return redirect(url_for('waiter'))
@app.route('/complete_order/<order_id>', methods=['GET', 'POST'])
def complete_order(order_id):
    order = db.Orders.query.get(order_id)
    if order:
        if order.cooked == True:
            db.Items.query.filter_by(order_id=order.order_id).delete()
            # Delete the order from the Orders table
            db.Orders.query.filter_by(order_id=order.order_id).delete()
            restaurant_db.session.commit()
            order.delivered = True
        elif order.cooked == False:
            db.Items.query.filter_by(order_id=order.order_id).delete()
            # Delete the order from the Orders table
            db.Orders.query.filter_by(order_id=order.order_id).delete()
            restaurant_db.session.commit()
    return redirect(url_for('waiter'))
@app.route('/delete_staff/<staff_id>', methods=['GET', 'POST'])
def delete_staff(staff_id):
    staff = db.StaffLogin.query.get(staff_id)
    db.StaffLogin.query.filter_by(staff_id=staff.staff_id).delete()
    restaurant_db.session.commit()
    return redirect(url_for('admin'))
    # function deletes staff from the StaffLogin table
@app.route('/add_staff', methods=['POST'])
def add_staff():
    staff_role = request.form['staff_role']
    username = request.form['username']
    password = request.form['password']
    staff = db.StaffLogin(staff_role=staff_role, username=username, password=password)
    restaurant_db.session.add(staff)
    restaurant_db.session.commit()
    return redirect(url_for('admin'))
    # function adds staff to the StaffLogin table
@app.route('/confirm_order/<order_id>', methods=['GET', 'POST'])
def confirm_order(order_id):
    order = db.Orders.query.get(order_id)
    order.confirmed = True
    restaurant_db.session.commit()
    return redirect(url_for('waiter'))
# function confirms order and changes order status from false to true when confirmed button is pressed.
@app.route('/kitchen')
def kitchen():
    orders = db.Orders.query.filter_by(delivered=False, confirmed=True, cooked=False).order_by(db.Orders.timeoforder.asc()).all()
    #orders shown only if delivered is false, confirned is true and cooked is false and orders them in ascending time.
    items = db.Items.query.join(db.Menu).add_columns(db.Menu.name, db.Menu.item_id, db.Items.quantity, db.Items.ready).all()
    return render_template('kitchen.html', items=items, orders=orders)
# function displays the orders in the kitchen webpage.
@app.route('/mark_as_ready', methods=['POST'] )
def mark_as_ready():
    item_id = request.form['item_id']
    item = db.Items.query.filter_by(item_id=item_id).first()
    if item:
        item.ready = True
        restaurant_db.session.commit()
        #Check if whole order is cooked
        if all(item.ready for item in item.order.items):
            item.order.cooked = True
            restaurant_db.session.commit()
            return jsonify({'message': 'Order complete, sent to waiters'})
        else:
            return jsonify({'message': 'Item marked as ready'})
    else:
        return jsonify({'message': 'Item not found'})
@app.route('/mark_as_not_ready', methods=['POST'] )
def mark_as_not_ready():
    item_id = request.form['item_id']
    item = db.Items.query.filter_by(item_id=item_id).first()
    if item:
        item.ready = False
        restaurant_db.session.commit()
        return "Items marked as not ready"
    else:
        return "Item not found"
@app.route('/admin')
def admin():
    staff_list = db.StaffLogin.query.all() #collects all the information from StaffLogin table.
    payment_info = db.PaymentHistory.query.all() #collects all the information from PaymentHistory table.
    return render_template('admin.html', staff_list=staff_list, payment_info=payment_info)
    #This function displays two tables information of all the present staff logins and payment history of all the orders.
@app.route('/modify_menu')
def modify_menu():
    menu_items = db.Menu.query.all()
    return render_template ('modifyMenu.html', menu_items = menu_items)
@app.route('/freezeItem/<item_id>', methods=['GET', 'POST'])
def freezeItem(item_id):
    item = db.Menu.query.get(item_id)
    if item == None:
        print("Item not found")
    elif item.available == False:
        item.available = True
    else:
        item.available  = False
    restaurant_db.session.commit()
    return modify_menu()
@app.route('/modifyItem/<item_id>/<part>/<newVal>', methods=['GET', 'POST'])
def modifyItem(item_id, part, newVal):
    item = db.Menu.query.get(item_id)
    if item == None:
        print("Item not found")
    elif part == "name":
        item.name = newVal
    elif part == "description":
        item.description = newVal
    elif part == "price":
        item.price = newVal
    elif part == "calories":
        item.calories = newVal
    elif part == "allergies":
        item.allergies = newVal
    else:
        item.item_type = newVal
    restaurant_db.session.commit()
    return modify_menu()
# Route to direct user to the menu page, not able to order off this page
@app.route('/menu')
def menu():
    menu_items = db.Menu.query.all()
    return render_template ('menu.html', menu_items = menu_items)
# Route to direct user to the about us page
@app.route('/aboutUs')
def aboutUs():
    return render_template ('aboutUs.html')
# Route to direct user to the help page
@app.route('/help')
def help():
    return render_template ('help.html')
@app.route('/staff_login', methods=['GET','POST'])
def staff_login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = db.StaffLogin.query.filter_by(username=username, password=password).first()
        if user:
            if user.staff_role.lower() == 'waiter':
                return redirect(url_for('waiter')) # Redirect the user to the waiter page
            elif user.staff_role.lower() == 'kitchen':
                return redirect(url_for('kitchen')) # Redirect the user to the kitchen page
            elif user.staff_role.lower() == 'admin':
                return redirect(url_for('admin')) # Redirect the user to the admin page
        else:
            error = 'Incorrect username or password, try again :)'
    return render_template('staffLogin.html', error=error)
if __name__ == '__main__':
    app.run(debug=True)
