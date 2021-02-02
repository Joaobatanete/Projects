import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    # check portfolio database.
    portfolio = db.execute("SELECT * FROM portfolio WHERE user_id = :user_id", user_id = session['user_id'])
    
    # check users actual cash.
    cash = db.execute("SELECT cash FROM users WHERE id = :u_id", u_id = session["user_id"])
    
    total_cash = float(cash[0]['cash'])
    
    return render_template("index.html", portfolio = portfolio, total_cash = total_cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    else:
        select = request.form.get("select")
        numb = request.form.get("number")
        
        if not select:
            return apology("must provide Stock", 403)
        if not numb:
            return apology("must provide Number of Stocks", 403)
            
        number = int(numb)
        
        if number < 1:
            return apology("0 or Negative Number of Stocks", 403)
            
        stock = lookup(select)
        
        if stock == None:
            return apology("Stock doesn't exist!", 403)
            
        price = float(stock["price"])
        
        # session["user_id"] was already atributed in login, so it can acess to the user cash.
        cash = db.execute("SELECT cash FROM users WHERE id = :u_id", u_id = session["user_id"])
        
        # cash will only return 1 row, so it picks the "cash" value from that row.                  
        current_cash = float(cash[0]["cash"])
        total = number * price
        
        if current_cash < total:
            return apology("You don't have enough cash for the transaction", 403)
            
        else:
            #update current user cash after purchase.
            current_cash -= total
            db.execute("UPDATE users SET cash = :cash  WHERE id = :u_id", cash = current_cash, u_id = session["user_id"])
            
            # select stock form portfolio.
            portfolio = db.execute("SELECT * FROM portfolio WHERE (user_id = :user_id AND Name = :Name)", user_id = session['user_id'], Name = stock['name'])
            
            # if it doesnt exists, creates Stock in Portfolio.
            if not portfolio:
                db.execute("INSERT INTO portfolio(user_id, Symbol, Name, Shares, Price, Total) VALUES(:user_id, :Symbol, :Name, :Shares, :Price, :Total)", user_id = session['user_id'], Symbol = stock['symbol'], Name = stock['name'], Shares = number, Price = stock['price'], Total = total)
            
            # else UPDATES Number of stock and Total spent, into portfolio.
            else:
                shares = int(portfolio[0]['Shares']) + number
                total_portfolio = int(portfolio[0]['Total']) + total
                db.execute("UPDATE portfolio SET Shares = :Shares, Total = :Total WHERE user_id = :user_id AND Name = :Name", Shares = shares, Total = total_portfolio, user_id = session['user_id'], Name = stock['name'])
            
            # Insert the Transaction into History database
            Action = "Bought"
            db.execute("INSERT INTO history(user_id, Action, Symbol, Name, Shares, Price, Total) VALUES(:user_id, :Action, :Symbol, :Name, :Shares, :Price, :Total)", user_id = session['user_id'], Action = Action, Symbol = stock['symbol'], Name = stock['name'], Shares = number, Price = stock['price'], Total = total)

            return redirect('/')


@app.route("/history")
@login_required
def history():
    # check Transaction database.
    history = db.execute("SELECT * FROM history WHERE user_id = :user_id", user_id = session['user_id'])
    
    return render_template("history.html", history = history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        
        if not symbol:
            return apology("must provide Symbol", 403)

        x = lookup(symbol)
        
        if x == None:
            return apology("Invalid Symbol", 403)
        else:
            return render_template("quoted.html", x = x)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        password_confirmation = request.form.get("password_confirmation")
        
        if not username:
            return apology("must provide username", 403)
        if not password and password_confirmation:
            return apology("must provide password", 403)
        
        if password != password_confirmation:
            return apology("Password confirmation not Equal", 403)
            
        rows = db.execute("SELECT username FROM users WHERE username = :username",
                          username=request.form.get("username"))
        if len(rows) > 0:
            return apology("username already exists", 403)
        
        # hash gonna store the password encripted, can check hash in sqlite after.    
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :password)", username = username, password = generate_password_hash(password))
        return redirect("/login")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "GET":
        return render_template("sell.html")
    else:
        select = request.form.get("select")
        numb = request.form.get("number")
        
        if not select:
            return apology("must provide Stock", 403)
        if not numb:
            return apology("must provide Number of Stocks", 403)
        
        number = int(numb)
        
        if number < 1:
            return apology("0 or Negative Number of Stocks", 403)
        
        # Check the current price of the Stock
        stock_lookup = lookup(select)
        
        if stock_lookup == None:
            return apology("Stock doesn't exist!", 403)
            
        Price = float(stock_lookup["price"])
        
        # Select the Stock form Portfolio database
        stock = db.execute("SELECT * FROM portfolio WHERE (user_id = :user_id AND Symbol = :Symbol)", user_id = session['user_id'], Symbol = select)
        
        if len(stock) == 0:
            return apology("You don't have this Stock!", 403)
        
        # Select the number of Shares from that Stock
        Shares = int(stock[0]["Shares"])
        
        if number > Shares:
            return apology("You don't have that amount of Shares to sell", 403)
        
        # Select Current Cash form the user.
        cash = db.execute("SELECT cash FROM users WHERE id = :u_id", u_id = session["user_id"])
        
        current_cash = float(cash[0]["cash"])
        
        # Total $ value from the selected stock shares
        total = number * Price
        
        # Update current user Cash after Sell, Number of Shares, Price of Share, and Total.
        current_shares = Shares - number
        current_cash += total
        total_stock = int(current_shares * Price)
        
        # Check if total stock isnt negative
        if total_stock < 0:
            return apology("Your total stock $ is negative, error.", 403)
        
        db.execute("UPDATE users SET cash = :cash  WHERE id = :u_id", cash = current_cash, u_id = session["user_id"])
        db.execute("UPDATE portfolio SET Shares = :Shares, Price = :Price, Total = :Total  WHERE user_id = :user_id AND Name = :Name", Shares = current_shares, Price = Price, Total = total_stock, user_id = session["user_id"], Name = stock[0]['Name'])
        
        # Insert the Transaction into History database
        Action = "Sold"
        db.execute("INSERT INTO history(user_id, Action, Symbol, Name, Shares, Price, Total) VALUES(:user_id, :Action, :Symbol, :Name, :Shares, :Price, :Total)", user_id = session['user_id'], Action = Action, Symbol = stock[0]['Symbol'], Name = stock[0]['Name'], Shares = number, Price = Price, Total = total)

        return redirect('/')


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
