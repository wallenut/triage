from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash
import numpy as np

from helpers import apology, login_required, lookup, usd

# % percentage over which to display a potential diagnosis
CUTOFF = 5

# Configure application
app = Flask(__name__)

# Ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///triage.db")

@app.route("/")
def index():
    """Handle requests for / via GET (and POST)"""
    if "user_id" in session.keys():
        print (session["user_id"])
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user for an account."""
    # POST
    if request.method == "POST":
        dup = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        if len(dup) != 0:
            return apology("username taken!")

        # Add user to database
        id = db.execute("INSERT INTO users (username, hash, doctor) VALUES (:username, :hash, :doctor)",
                        username=request.form.get("username"),
                        hash=generate_password_hash(request.form.get("password")),
                        doctor=int(request.form.get("doctor") == "yes"))
        # Log user in
        session["user_id"] = id

        # Let user know they're registered
        flash("Registered!")
        return redirect("/")

    # GET
    else:
        return render_template("register.html")

@app.route("/addLikelihoods", methods=["GET", "POST"])
# @login_required
def addLikelihoods():
    """Handle requests for / via GET (and POST)"""
    if request.method == "GET":
        principals = db.execute("SELECT id, name FROM principals")
        return render_template("select_diagnosis.html", principals=principals, action="addLikelihoods")
    elif request.method == "POST":
        req = request.form.to_dict()
        if "newPrincipal" in req:
            add_principals(req["newPrincipal"])
            principal = db.execute("SELECT id FROM principals WHERE name = :name", name=req["newPrincipal"])[0]["id"]
        else:
            principal = request.form.get("principal_id")
        oldLikelihoods = db.execute("SELECT * FROM likelihoods WHERE principal = :principal", principal=principal);
        d = get_diagnoses()
        q = get_questions()
        likelihoodMatrix = [[1 for x in range(len(d))] for y in range(len(q))]
        # print (oldLikelihoods)
        questions = list(map((lambda x: x["question"]), q))
        diagnoses = list(map((lambda x: x["name"]), d))
        print(questions)
        print(diagnoses)
        for likelihood in oldLikelihoods:
            likelihoodMatrix[likelihood["question"] - 1][likelihood["diagnosis"] - 1] = likelihood["likelihood"]
        print (likelihoodMatrix)
        print (principal)
        return render_template("updateLikelihoods.html", principal=principal, likelihoodMatrix=likelihoodMatrix, questions=questions, diagnoses=diagnoses)

@app.route("/updateLikelihoods", methods=["POST"])
# @login_required
def updateLikelihoods():
    print("in update likelihoods")
    updateMatrix = request.form.to_dict()
    updateMatrix.pop("update", None)
    p = int(updateMatrix["principal"])
    updateMatrix.pop("principal", None)
    print(updateMatrix)
    for k in updateMatrix:
        if updateMatrix[k] == "1":
            continue
        #split to get question and diagnosis number
        qdList = k.split(",")
        q = int(qdList[0])
        d = int(qdList[1])
        l = float(updateMatrix[k])
        updateTest = db.execute("SELECT likelihood FROM likelihoods WHERE principal = :p AND diagnosis = :d AND question = :q", p=p, d=d, q=q)
        #if we are to update or insert this new likelihood
        if len(updateTest):
            db.execute("UPDATE likelihoods SET likelihood = :l WHERE principal = :p AND diagnosis = :d AND question = :q", l=l, p=p, d=d, q=q)
        else:
            #we have to insert a new likelihood
            add_likelihoods(p, d, q, l)
        return redirect("/")

@app.route("/logout", methods=["GET"])
def logout():
    session.clear()
    return redirect("/")

@app.route("/login", methods=["GET", "POST"])
def login():

    if "user_id" in session.keys():
        return redirect("/")
    elif request.method == "GET":
        return render_template("login.html")
    else:
        session.clear()

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

@app.route("/diagnose", methods=["GET", "POST"])
# @login_required
def diagnose():
    #display the principals listed as a select option
    if request.method == "GET":
        principals = db.execute("SELECT id, name FROM principals")
        return render_template("select_diagnosis.html", principals=principals, action="diagnose")
    elif request.method == "POST":
        principal = request.form.get("principal_id")
        print (principal)
        questions = db.execute("SELECT id, question FROM questions");
        return render_template("questions.html", principal=principal, questions=questions)

@app.route("/probabilities", methods=["POST"])
# @login_required
def probabilities():
    #display the principals listed as a select option
    data = request.form.to_dict()
    principal = int(data['principal'])
    patient = list(map(int, list(data.values())[1:]))
    return calculate_probabilities(principal, patient)

####################
####  Methods  #####
####################

def calculate_probabilities(principal, patient):
    """Given principal symptom id, patient answers (in matrix format), return likelihood calculations"""

    # pf = open('patient_findings.csv', 'r')
    # patient = np.array(list(csv.reader(pf))).T.astype(int)

    # extract relevant cells
    print("in calculate")
    diagnoses = np.array(get_diagnoses())
    print(diagnoses)
    cough_likelihoods = get_table(principal).astype(float)
    patient = np.array(patient).astype(float)
    print(patient.shape)

    # convert to patient-specific probabilities
    relevant_symptoms = cough_likelihoods * patient.reshape(-1, 1)
    print(relevant_symptoms.shape)
    relevant_symptoms [relevant_symptoms == 0] = 1

    # calculate and normalize likelihoods
    prods = np.prod(relevant_symptoms, axis=0)
    norm = np.sum(prods)
    percentages = (prods * 100 / norm).astype(float)

    # gather diagnoses above cutoff
    perc_over = percentages[percentages > CUTOFF]
    labels_over = diagnoses[np.where(percentages > CUTOFF)[0]]
    print(labels_over)

    # print diagnoses
    return render_template("results.html", percents=perc_over, labels=labels_over)

def get_table(principal):
    """Given principal symptom id, get all likelihoods for it and fill empty table positions with 1s"""
    questions = get_questions()
    diagnoses = get_diagnoses()

    q_len = len(questions)
    d_len = len(diagnoses)

    tb = np.zeros([q_len, d_len])
    likelihoods = get_likelihoods(principal)

    for liks in likelihoods:
        p, d, q, l = liks['principal'], liks['diagnosis'], liks['question'], liks['likelihood']
        tb[q - 1][d - 1] = l
    tb[tb == 0] = 1 # fill rest with ones

    return tb

####################
### database API ###
####################

# diagnoses #
def get_diagnoses():
    return db.execute("SELECT * FROM diagnoses")

def add_diagnosis(name):
    if db.execute("INSERT INTO diagnoses (name) VALUES (:name)", name=name) is None:
        return False
    return True

# questions #
def get_questions():
    return db.execute("SELECT * FROM questions")

def add_questions(question):
    if db.execute("INSERT INTO questions (question) VALUES (:q)", q=question) is None:
        return False
    return True

# principals #
def get_principals():
    return db.execute("SELECT * FROM principals")

def add_principals(name):
    if db.execute("INSERT INTO principals (name) VALUES (:name)", name=name) is None:
        return False
    return True

# likelihoods #
def add_likelihoods(principal, diagnosis, question, likelihood):
    if db.execute("INSERT INTO likelihoods (principal, diagnosis, question, likelihood) VALUES (:p, :d, :q, :l)",
        p=principal, d=diagnosis, q=question, l=likelihood) is None:
        return False
    return True

def get_likelihoods(principal):
    """Given principal symptom id, return all likelihood info"""
    return db.execute("SELECT * FROM likelihoods WHERE principal = :p", p=principal)
