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

####################
#### Endpoints  ####
####################

@app.route("/")
def index():
    """Handle requests for / via GET (and POST)"""
    name = ""
    if "user_id" in session.keys():
        name = db.execute("SELECT username FROM users WHERE id = :i", i=session["user_id"])[0]["username"]
        user_history = db.execute("SELECT history.timestamp as timestamp, history.id as history_id, history.user_id as user_id, principals.id as principal_id, principals.name as principal_name FROM\
        history JOIN principals ON history.principal_id = principals.id WHERE history.user_id = :u GROUP BY history.id", u = session["user_id"])
        if len(user_history):
            return render_template("index.html", history=user_history, name=name)
    return render_template("index.html", history=[], name=name)

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
        if int(request.form.get("doctor") == "yes"):
            session["doctor"] = 1

        # Let user know they're registered
        flash("Registered!")
        return redirect("/")

    # GET
    else:
        return render_template("register.html")

@app.route("/history", methods=["POST"])
def history():
    """Display a user's prior results."""
    # POST
    if request.method == "POST":
        history_id = request.form.get("history_id")
        results = db.execute("SELECT * FROM patient_results WHERE history = :h", h=history_id)
        labels = [{'id':result["diagnosis_id"], 'name': result["diagnosis_name"]} for result in results]
        percents = [ result["probability"] for result in results]
        return render_template("results.html", percents=percents, labels=labels)
    # GET
    else:
        return redirect("/")

@app.route("/addLikelihoods", methods=["GET", "POST"])
def addLikelihoods():
    """Handle requests for adding likelihoods via GET (and POST)"""
    # Permissions
    if "user_id" not in session or "doctor" not in session:
        return redirect("/")
    # GET
    elif request.method == "GET":
        principals = db.execute("SELECT id, name FROM principals")
        return render_template("select_diagnosis.html", principals=principals, action="addLikelihoods")
    # POST
    elif request.method == "POST":
        req = request.form.to_dict()
        # Adding likelihoods
        if "newPrincipal" in req and len(req["newPrincipal"]) > 0:
            add_principals(req["newPrincipal"])
            principal = db.execute("SELECT id FROM principals WHERE name = :name", name=req["newPrincipal"])[0]["id"]
        # Updating likelihoods
        elif "principal_id" in req:
            principal = req["principal_id"]
        # No likelihood submitted
        else:
            return render_template("error.html", message="No principal selected or added.")
        # Query old likelihoods and format into matrix to update or add
        oldLikelihoods = db.execute("SELECT * FROM likelihoods WHERE principal = :principal", principal=principal);
        d = get_diagnoses()
        q = get_questions()
        likelihoodMatrix = [[1 for x in range(len(d))] for y in range(len(q))]
        questions = list(map((lambda x: x["question"]), q))
        diagnoses = list(map((lambda x: x["name"]), d))
        for likelihood in oldLikelihoods:
            likelihoodMatrix[likelihood["question"] - 1][likelihood["diagnosis"] - 1] = likelihood["likelihood"]
        return render_template("updateLikelihoods.html", principal=principal, likelihoodMatrix=likelihoodMatrix, questions=questions, diagnoses=diagnoses)

@app.route("/updateLikelihoods", methods=["GET", "POST"])
def updateLikelihoods():
    """Handle requests for updating likelihoods via GET (and POST)"""
    # Permissions
    if request.method == "GET" or "user_id" not in session or "doctor" not in session:
        return redirect("/")
    updateMatrix = request.form.to_dict()
    updateMatrix.pop("update", None)
    p = int(updateMatrix["principal"])
    updateMatrix.pop("principal", None)
    for k in updateMatrix:
        if updateMatrix[k] == "1":
            continue
        # Split to get question and diagnosis number
        qdList = k.split(",")
        q = int(qdList[0])
        d = int(qdList[1])
        l = float(updateMatrix[k])
        updateTest = db.execute("SELECT likelihood FROM likelihoods WHERE principal = :p AND diagnosis = :d AND question = :q", p=p, d=d, q=q)
        # Update existing likelihood
        if len(updateTest):
            db.execute("UPDATE likelihoods SET likelihood = :l WHERE principal = :p AND diagnosis = :d AND question = :q", l=l, p=p, d=d, q=q)
        # Add new likelihood
        else:
            add_likelihoods(p, d, q, l)
        return redirect("/")

@app.route("/logout", methods=["GET"])
def logout():
    """Clears session and logs user out."""
    session.clear()
    return redirect("/")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Handle requests for login via GET (and POST)"""
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

        if int(rows[0]["doctor"]) == 1:
            session["doctor"] = 1

        # Redirect user to home page
        return redirect("/")

@app.route("/diagnose", methods=["GET", "POST"])
def diagnose():
    """Handle requests for diagnosing symptoms via GET (and POST)"""
    # Permissions
    if "user_id" not in session:
        return redirect("/")
    # GET
    elif request.method == "GET":
        principals = db.execute("SELECT id, name FROM principals")
        return render_template("select_diagnosis.html", principals=principals, action="diagnose")
    # POST
    elif request.method == "POST":
        req = request.form.to_dict()
        if "principal_id" not in req:
            return render_template("error.html", message="No principal symptom selected to diagnose.")
        principal = req["principal_id"]
        questions = db.execute("SELECT id, question FROM questions");
        history_id = db.execute("INSERT INTO history (user_id, principal_id) VALUES (:u, :p)", u=session["user_id"], p=principal)
        return render_template("personalInfo.html", history=history_id, questions=questions)

@app.route("/personalInfo", methods=["GET", "POST"])
def personalInfo():
    """Handle requests for processing personal information via GET (and POST)"""
    # Permissions
    if request.method == "GET" or "user_id" not in session:
        return redirect("/")

    # Processes answered questions
    data = request.form.to_dict()
    history = int(data["history"])
    answers = []
    for i in range(5):
        if "age_range" in data.keys() and i + 1 == int(data["age_range"]):
            answers.append(1)
        else:
            answers.append(0)
    answers.append(int(data["6"]))
    # Adding default value of 0 for ethnicity - non discrete variable
    answers.append(0)
    data.pop("history", None)
    data.pop("age_range", None)
    data.pop("6", None)
    return render_template("/symptomContext.html", history=history, answers=answers, questions=data)

@app.route("/symptomContext", methods=["GET", "POST"])
def symptomContext():
    """Handle requests for processing symptom context via GET (and POST)"""
    # Permissions
    if request.method == "GET" or "user_id" not in session:
        return redirect("/")
    history, answers, questions = display_questions(16)
    return render_template("/symptomDescriptions.html", history=history, answers=answers, questions=questions)

@app.route("/symptomDescriptions", methods=["GET", "POST"])
def symptomDescriptions():
    """Handle requests for processing symptom descriptions via GET (and POST)"""
    # Permissions
    if request.method == "GET" or "user_id" not in session:
        return redirect("/")
    history, answers, questions = display_questions(20)
    return render_template("/coughQuestions.html", history=history, answers=answers, questions=questions)

@app.route("/coughQuestions", methods=["GET", "POST"])
def coughQuestions():
    """Handle requests for processing cough via GET (and POST)"""
    # Permissions
    if request.method == "GET" or "user_id" not in session:
        return redirect("/")
    history, answers, questions = display_questions(26)
    return render_template("/bodyTemperature.html", history=history, answers=answers, questions=questions)

@app.route("/bodyTemperature", methods=["GET", "POST"])
def bodyTemperature():
    """Handle requests for processing temperature via GET (and POST)"""
    # Permissions
    if request.method == "GET" or "user_id" not in session:
        return redirect("/")
    history, answers, questions = display_questions(29)
    return render_template("/chillsQuestions.html", history=history, answers=answers, questions=questions)

@app.route("/chillsQuestions", methods=["GET", "POST"])
def chillsQuestions():
    """Handle requests for processing chills via GET (and POST)"""
    # Permissions
    if request.method == "GET" or "user_id" not in session:
        return redirect("/")
    history, answers, questions = display_questions(36)
    return render_template("/noseEyes.html", history=history, answers=answers, questions=questions)

@app.route("/noseEyes", methods=["GET", "POST"])
def noseEyes():
    """Handle requests for processing information via GET (and POST)"""
    # Permissions
    if request.method == "GET" or "user_id" not in session:
        return redirect("/")
    history, answers, questions = display_questions(41)
    return render_template("/headPain.html", history=history, answers=answers, questions=questions)

@app.route("/headPain", methods=["GET", "POST"])
def headPain():
    """Handle requests for processing information via GET (and POST)"""
    # Permissions
    if request.method == "GET" or "user_id" not in session:
        return redirect("/")
    history, answers, questions = display_questions(48)
    return render_template("/musclePain.html", history=history, answers=answers, questions=questions)

@app.route("/musclePain", methods=["GET", "POST"])
def musclePain():
    """Handle requests for processing muscle information via GET (and POST)"""
    # Permissions
    if request.method == "GET" or "user_id" not in session:
        return redirect("/")
    history, answers, questions = display_questions(55)
    return render_template("/duration.html", history=history, answers=answers, questions=questions)

@app.route("/duration", methods=["GET", "POST"])
def duration():
    """Handle requests for processing duration via GET (and POST)"""
    # Permissions
    if request.method == "GET" or "user_id" not in session:
        return redirect("/")
    history, answers, questions = display_questions(62)
    return render_template("/specifics.html", history=history, answers=answers, questions=questions)

@app.route("/specifics", methods=["GET", "POST"])
def specifics():
    """Handle requests for processing specific information via GET (and POST)"""
    # Permissions
    if request.method == "GET" or "user_id" not in session:
        return redirect("/")
    history, answers, questions = display_questions(78)
    return render_template("/smoking.html", history=history, answers=answers, questions=questions)

@app.route("/smoking", methods=["GET", "POST"])
def smoking():
    """Handle requests for processing smoking and calculating likelihoods via GET (and POST)"""
    # Permissions
    if request.method == "GET" or "user_id" not in session:
        return redirect("/")
    data = request.form.to_dict()
    history = int(data["history"])

    data.pop("history", None)
    answers = [int(data[str(i)]) for i in range(1, 93)]

    for i in range(1, 93):
        db.execute("INSERT INTO patient_input (history, question, response) VALUES (:h, :q, :r)", h=history, q=i, r=int(data[str(i)]))

    row = db.execute("SELECT principal_id FROM history WHERE id = :h", h=history)
    if len(row) == 1:
        return calculate_probabilities(int(row[0]["principal_id"]), answers, history)
    else:
        return render_template("error.html", message="Unexpected error calculating likelihoods. No principal symptom entered.")

####################
####  Methods  #####
####################

def display_questions(n):
    data = request.form.to_dict()
    history = int(data["history"])

    data.pop("history", None)
    answers = [data[str(i)] for i in range(1, n + 1)]
    questions = {key: data[key] for key in data if int(key) > n}

    return history, answers, questions

def calculate_probabilities(principal, patient, history):
    """Given principal symptom id, patient answers, return likelihood calculations"""

    # extract relevant cells
    diagnoses = np.array(get_diagnoses())

    cough_likelihoods = get_table(principal).astype(float)
    patient = np.array(patient).astype(float)

    # convert to patient-specific probabilities
    relevant_symptoms = cough_likelihoods * patient.reshape(-1, 1)
    relevant_symptoms [relevant_symptoms == 0] = 1

    # calculate and normalize likelihoods
    prods = np.prod(relevant_symptoms, axis=0)
    norm = np.sum(prods)
    percentages = (prods * 100 / norm).astype(float)

    # gather diagnoses above cutoff
    perc_over = percentages[percentages > CUTOFF]
    labels_over = diagnoses[np.where(percentages > CUTOFF)[0]]

    # store diagnosis id, name, and probability in results table
    for i in range(len(labels_over)):
        db.execute("INSERT INTO patient_results (history, diagnosis_id, diagnosis_name, probability) VALUES (:h, :di, :dn, :p)", h=history, di=labels_over[i]["id"], dn=labels_over[i]["name"], p=perc_over[i])

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
    """ Returns list of diagnoses from database """
    return db.execute("SELECT * FROM diagnoses")

def add_diagnosis(name):
    """ Adds a new diagnosis to the database """
    if db.execute("INSERT INTO diagnoses (name) VALUES (:name)", name=name) is None:
        return False
    return True

# questions #
def get_questions():
    """ Returns list of questions from database """
    return db.execute("SELECT * FROM questions")

def add_questions(question):
    """ Adds a new question to the database """
    if db.execute("INSERT INTO questions (question) VALUES (:q)", q=question) is None:
        return False
    return True

# principals #
def get_principals():
    """ Returns list of principals from database """
    return db.execute("SELECT * FROM principals")

def add_principals(name):
    """ Adds a new principal to the database """
    if db.execute("INSERT INTO principals (name) VALUES (:name)", name=name) is None:
        return False
    return True

# likelihoods #
def add_likelihoods(principal, diagnosis, question, likelihood):
    """ Adds a likelihood value to the database """
    if db.execute("INSERT INTO likelihoods (principal, diagnosis, question, likelihood) VALUES (:p, :d, :q, :l)",
        p=principal, d=diagnosis, q=question, l=likelihood) is None:
        return False
    return True

def get_likelihoods(principal):
    """Given principal symptom id, return all likelihood info"""
    return db.execute("SELECT * FROM likelihoods WHERE principal = :p", p=principal)
