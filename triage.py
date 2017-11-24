import numpy as np
import csv

# % percentage over which to display a potential diagnosis
CUTOFF = 5

# import cough likelihoods
cf = open('cough_likelihoods.csv', 'r')
cough_data = np.array(list(csv.reader(cf)))

# import patient findings
pf = open('patient_findings.csv', 'r')
patient = np.array(list(csv.reader(pf))).T.astype(int)

# extract relevant cells
features = cough_data[1:, 0]
diagnoses = cough_data[0, 1:]
cough_likelihoods = cough_data[1:, 1:].astype(float)

# convert to patient-specific probabilities
relevant_symptoms = cough_likelihoods * patient.T
relevant_symptoms [relevant_symptoms == 0] = 1

# calculate and normalize likelihoods
prods = np.prod(relevant_symptoms, axis=0)
norm = np.sum(prods)
percentages = (prods * 100 / norm).astype(float)

 # gather diagnoses above cutoff
perc_over = percentages[percentages > CUTOFF]
labels_over = diagnoses[np.where(percentages > CUTOFF)[0]]

# print diagnoses
for i in range(len(labels_over)):
	print(labels_over[i].ljust(40) + "with probability " + str(perc_over[i]))
