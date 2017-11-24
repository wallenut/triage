from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

import numpy as np
import csv
# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///triage.db")

d = ["Viral infection","Post-viral cough","Influenza","Pertussis","Pneumonia",	"TB","Bacterial sinusitis","Stable asthma","Asthma exacerbation","Stable COPD","COPD exacerbation","Stable bronchiectasis","Bronchiectasis exacerbation","Reflux","Post-nasal drip","ACE inhibitor","Pulmonary embolism","Heart failure","Lung cancer","Aspiration","Interstitial lung disease","Occupational / irritant exposure","Disorder of the ears"]
q=["< 40",
"40 - 50",
"50 - 60",
"60 - 80",
">80",
"Gender (if female)",
"Ethnicity",
"Not influenza season",
"Sick contact",
"Contact with influenza",
"Contact with pertussis",
"Started ACE inhibitor",
"Exposure to allergen",
"Exposure to irritant",
"After extended travel",
"After prolonged period of immobility",
"Started with cold, but did not completely resolve",
"Occurs in the morning",
"Worse when lying down",
"Worse after exercise",
"Dry",
"Clear sputum",
"Discolored sputum",
"Bloody sputum (<1 teaspoon per hour)",
"Bloody sputum (> a few teaspoons per hour)",
"Chronic sputum, but now more than usual",
"Fevers",
"| > 38.0 C",
"| > 40.0 C",
"Chills",
"| Intense shaking chills",
"Night sweats",
"| Wet forehead",
"| Have to change clothes",
"Unintentional weight loss",
"| > 10 lbs in the last month",
"Runny nose",
"|Clear discharge",
"|Thick, green / yellow discharge",
"|Got better, now worsening",
"Watery eyes",
"Sore throat",
"|White exudate in throat",
"Enlarged lymph nodes",
"Headache",
"|Ache in face, below eyes",
"Ear pain",
"New trouble hearing",
"Chest pain",
"Breathing is comfortable",
"Mild shortness of breath",
"Severe shortness of breath",
"Muscle aches",
"Heartburn",
"Trouble swallowing",
"<1 weeks",
"2 - 3 weeks",
"3 - 8 weeks",
"> 8 weeks",
"If < 3 weeks, does patient report frequent episodes / worsenings",
"If < 3 weeks, does patient report similar to previous episode / worsening",
"If < 3 weeks, does patient report rarely having symptoms like this",
"Asthma",
"COPD or emphysema",
"Cystic Fibrosis",
"Heart Failure",
"Pneumonia",
"Immunosuppression",
"Recent chemotherapy",
"Organ transplant",
"Stroke",
"GERD / Acid reflux",
"Recent lung / abdominal surgery",
"ACE inhibitor, < 6 months",
"ACE inhibitor, > 6 months",
"No ACE inibitor",
"Cystic fibrosis",
"Other lung disease",
"Non-smoker",
"<20 pack years",
"20 - 40 pack years",
"> 40 pack years",
"Illicit substance use",
"Asbestos exposure",
"Working with imprisoned population",
"Lived in TB endemic area",
"Febrile",
"Tachycardic",
"Tachypneic",
"Wheezes",
"Diminished breath sounds",
"Focal consolidation"]

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
    """Add likelihood for given principal, diagnosis, question combination"""
    if db.execute("INSERT INTO likelihoods (principal, diagnosis, question, likelihood) VALUES (:p, :d, :q, :l)",
        p=principal, d=diagnosis, q=question, l=likelihood) is None:
        return False
    return True

def get_likelihoods(principal):
    """Given principal symptom id, return all likelihood info"""
    return db.execute("SELECT * FROM likelihoods WHERE principal = :p", p=principal)

def get_table(principal):
    """Given principal symptom id, get all likelihoods for it and fill empty table positions with 1s"""
    questions = get_questions()
    diagnoses = get_diagnoses()

    q_len = len(questions)
    d_len = len(diagnoses)

    tb = np.zeros([q_len+1, d_len+1])
    likelihoods = get_likelihoods(principal)

    for liks in likelihoods:
        p, d, q, l = liks['principal'], liks['diagnosis'], liks['question'], liks['likelihood']
        tb[q][d] = l
    tb[tb == 0] = 1 # fill rest with ones

    return tb

get_table(1)
#for i in d:
    #db.execute("INSERT INTO diagnoses (name) VALUES (:name)", name=i)
#for i in q:
    #db.execute("INSERT INTO questions (question) VALUES (:q)", q=i)

# id = db.execute("SELECT * FROM principals WHERE name = :name", name="cough")
# print(id)
d = get_diagnoses()
q = get_questions()

# Import table
# import csv
# cf = open('cln.csv', 'r')
# c = np.array(list(csv.reader(cf)))
# pr = 1
# for i,qu in enumerate(q):
#     for j,di in enumerate(d):
#         print(f"Principal {pr}, question {qu}, diagnosis {di}, lik {c[i,j]}")
#         if float(c[i][j]) != 1.0:
#             db.execute("INSERT INTO likelihoods (principal, diagnosis, question, likelihood) VALUES (:p,:d,:q,:l)", p=pr, d=di["id"], q=qu['id'], l=float(c[i][j]))
# print(c)