"""
Runs the Gurobi linear optimizer on the planning problem.
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from gurobipy import Model, GRB, quicksum

# PREPROCESSING

# Open the json file
JSON_PATH = "data/medium_instance.json"
f = open(JSON_PATH, encoding="utf-8")
data = json.load(f)

# List the days, the qualifications, the workers and the jobs
list_days = range(1, data["horizon"] + 1)
list_quals = data["qualifications"]
list_workers = [x["name"] for x in data["staff"]]
list_jobs = [x["name"] for x in data["jobs"]]

# Create utility dictionaries
conge, qualifie, requirements, gain, penalite, itstoolate = {}, {}, {}, {}, {}, {}

# Fill the dictionaries
for personne in data["staff"]:
    worker = personne["name"]
    for qual in list_quals:
        # qualifie is a binary variable that is 1 if the worker has the qualification
        qualifie[worker, qual] = 1 * (qual in personne["qualifications"])

    for day in list_days:
        # conge is a binary variable that is 1 if the worker is on vacation
        conge[worker, day] = 1 * (day in personne["vacations"])

for projet in data["jobs"]:
    job = projet["name"]
    # gain is the reward of the job
    gain[job] = projet["gain"]

    for day in list_days:
        # itstoolate is a binary variable that is 1 if the job is late on the day
        itstoolate[job, day] = 1 * (day > projet["due_date"])

    # penalite is the daily penalty of the job
    penalite[job] = projet["daily_penalty"]

    for qual in list_quals:
        if qual in projet["working_days_per_qualification"]:
            # requirements is the number of days the job requires the qualification
            requirements[job, qual] = projet["working_days_per_qualification"][qual]
        else:
            requirements[job, qual] = 0

# Create the model
m = Model("Projet_SDP")
chosenjob = {}
planning = {}
estaffecte = {}
workedtoday = {}
begin, end = {}, {}

# Create the variables
for job in list_jobs:
    chosenjob[job] = m.addVar(vtype=GRB.BINARY, name=f"chosenjob_{job}")
    begin[job] = m.addVar(vtype=GRB.INTEGER, lb=0, name=f"begin_{job}")
    end[job] = m.addVar(vtype=GRB.INTEGER, lb=0, name=f"end_{job}")

    for worker in list_workers:
        estaffecte[worker, job] = m.addVar(
            vtype=GRB.BINARY, name=f"estafecte_{worker}_{job}"
        )

        for qual in list_quals:
            for day in list_days:
                planning[worker, qual, day, job] = m.addVar(
                    vtype=GRB.BINARY,
                    name=f"planning_{worker}_{qual}_{day}_{job}",
                )

    for day in list_days:
        workedtoday[job, day] = m.addVar(
            vtype=GRB.BINARY, name=f"workedtoday_{job}_{day}"
        )

# Objective functions
nbmaxjobs = m.addVar(vtype=GRB.INTEGER, lb=0, name="nbmaxjobs")
maxlenjob = m.addVar(vtype=GRB.INTEGER, lb=0, name="maxlenjob")

# Create the constraints
for worker in list_workers:

    # Definition de nbmaxjobs
    m.addConstr(quicksum([estaffecte[worker, job] for job in list_jobs]) <= nbmaxjobs)

    for day in list_days:
        # Contrainte d'unicité d'affectation
        m.addConstr(
            quicksum(
                np.array(
                    [
                        [planning[worker, qual, day, job] for qual in list_quals]
                        for job in list_jobs
                    ]
                ).flatten()
            )
            <= 1
        )
        for qual in list_quals:
            for job in list_jobs:
                # Contrainte de qualification
                m.addConstr(planning[worker, qual, day, job] <= qualifie[worker, qual])
                # Contrainte de conge
                m.addConstr(planning[worker, qual, day, job] + conge[worker, day] <= 1)
                # definition de estaffecte(worker,job)
                m.addConstr(estaffecte[worker, job] >= planning[worker, qual, day, job])
                # definition de workedtoday(job,day)
                m.addConstr(planning[worker, qual, day, job] <= workedtoday[job, day])

M = 10**6

for job in list_jobs:
    m.addConstr(1 + end[job] - begin[job] <= maxlenjob)

    for day in list_days:
        # definition de begin(job)
        m.addConstr(day - begin[job] >= M * (workedtoday[job, day] - 1))
        # definition de end(job)
        m.addConstr(end[job] - day >= M * (workedtoday[job, day] - 1))

    for qual in list_quals:
        # Contrainte de completion des projets
        m.addConstr(
            requirements[job, qual] - M * (1 - chosenjob[job])
            <= quicksum(
                np.array(
                    [
                        [planning[worker, qual, day, job] for worker in list_workers]
                        for day in list_days
                    ]
                ).flatten()
            )
        )

# Create objective function
argent = quicksum(
    [
        gain[job] * chosenjob[job]
        - quicksum(
            [
                itstoolate[job, day] * workedtoday[job, day] * penalite[job]
                for day in list_days
            ]
        )
        for job in list_jobs
    ]
)
m.setObjective(argent, GRB.MAXIMIZE)

# Run the model
m.optimize()

# Print the results
print("travail:")
for job in list_jobs:
    if chosenjob[job].x == 1:
        print(f"chosenjob[{job}]=1")
    for worker in list_workers:
        if estaffecte[worker, job].x == 1:
            print(f"estaffecte[{worker},{job}]=1")
        for day in list_days:
            for qual in list_quals:
                if planning[worker, qual, day, job].x == 1:
                    print(f"planning[{worker}, {qual}, {day}, {job}]=1")

# Plot the results
fig, ax = plt.subplots()
ax.set_title("Planning")
ax.set_xlabel("Jour")
ax.set_ylabel("Worker")
# Set xticks
ax.set_xticks(list_days)

# Map a color to each qualification
qual_color = {}
colors = [
    "red",
    "blue",
    "green",
    "yellow",
    "orange",
    "purple",
    "pink",
    "brown",
    "gray",
    "olive",
    "cyan",
]
for i, qual in enumerate(list_quals):
    qual_color[qual] = i

for job in list_jobs:
    if chosenjob[job].x == 1:
        for worker in list_workers:
            for day in list_days:
                for qual in list_quals:
                    if planning[worker, qual, day, job].x == 1:
                        ax.barh(
                            worker,
                            1,
                            left=day - 1,
                            color=colors[qual_color[qual]],
                            label=qual,
                        )
# Add a legend for the colors quals
handles, labels = ax.get_legend_handles_labels()
by_label = dict(zip(labels, handles))
ax.legend(by_label.values(), by_label.keys())
plt.show()
