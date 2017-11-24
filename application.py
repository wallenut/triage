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
    """Handle requests for / via GET (and POST)"""
    if "user_id" in session.keys():
        return redirect("/")
    elif request.method == "GET":
        return render_template("register.html")
    else:
        session["user_id"] = request.form.get("username")
        return redirect("/")

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session.keys():
        return redirect("/")
    elif request.method == "GET":
        return render_template("register.html")
    else:
        session["user_id"] = request.form.get("username")
        return redirect("/")

@app.route("/diagnose", methods=["GET", "POST"])
# @login_required
def diagnose():
    #display the principals listed as a select option
    if request.method == "GET":
        principals = db.execute("SELECT id, name FROM principals");
        return render_template("select_diagnosis.html", principals=principals)
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
    calculate_probabilities(principal, patient)
    return redirect("/")

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
    for i in range(len(labels_over)):
    	print(labels_over[i]["name"].ljust(40) + "with probability " + str(perc_over[i]))

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

def add_principles(name):
    if db.execute("INSERT INTO principles (name) VALUES (:name)", name=name) is None:
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