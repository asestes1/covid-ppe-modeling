import sys
import os
import pandas
import shutil

import scipy.stats
import simpy
import ppe.framework
import ppe.implement

project_dir = os.path.abspath(os.path.join(os.path.join(__file__, os.pardir), os.pardir))
ppe_dir = os.path.abspath(os.path.join(project_dir, "ppe"))
resource_dir = os.path.abspath(os.path.join(project_dir, "resources"))
results_dir = os.path.abspath(os.path.join(project_dir, "generated_results"))
if not os.path.isdir(results_dir):
    os.mkdir(results_dir)

sim_results_dir = os.path.abspath(os.path.join(results_dir, "sim_results"))
if not os.path.isdir(sim_results_dir):
    os.mkdir(sim_results_dir)

shutil.copyfile(__file__, os.path.join(sim_results_dir, "simscript.py"))

sys.path.insert(0, ppe_dir)

minutes_per_day = 60 * 24
icu_survival_probs = {ppe.framework.InfectionSeverity.REQ_VENT: 0.5}
noicu_survival_probs = {ppe.framework.InfectionSeverity.REQ_VENT: 0.05}
icu_dist = {ppe.framework.InfectionSeverity.REQ_VENT: 1}
stay_dists = {ppe.framework.InfectionSeverity.REQ_VENT: scipy.stats.poisson(mu=10 * minutes_per_day)}

icu_demand_filepath = os.path.abspath(os.path.join(resource_dir, "icu_demand.csv"))
est_icu_demands = pandas.read_csv(icu_demand_filepath).values.ravel()


def interarrival_function(x: float) -> float:
    day_index = int(x / minutes_per_day)
    return minutes_per_day / (est_icu_demands[day_index] / 3.0)


for i in range(150, 310, 10):
    for j in range(30, 50):
        print(i, j)
        env = simpy.Environment()
        myhospital = ppe.implement.HospitalStateImpl(existing_patients={}, bedusers=set(), ventusers=set())
        mypolicy = ppe.implement.FirstComeFirstServedPolicy(max_beds=i, max_ventilators=i)
        model = ppe.implement.HospitalModelImpl(icu_survivalprobs=icu_survival_probs,
                                                noicu_survivalprobs=noicu_survival_probs,
                                                severity_dist=icu_dist,
                                                stay_dists=stay_dists,
                                                interarrival_function=interarrival_function, seed=j)

        event_outpath = os.path.abspath(os.path.join(sim_results_dir, "event_out" + str(i) + "_" + str(j) + ".csv"))
        patient_outpath = os.path.abspath(os.path.join(sim_results_dir, "patient_out" + str(i) + "_" + str(j) + ".csv"))
        with open(event_outpath, 'w') as event_file:
            with open(patient_outpath, 'w') as patient_file:
                sim_process = ppe.framework.icu_process(env=env, hospital_state=myhospital,
                                                        logger=ppe.implement.CSVLogger(event_file=event_file,
                                                                                       patient_file=patient_file),
                                                        policy=mypolicy, model=model)

                env.process(sim_process)
                env.run(120 * minutes_per_day - 1)