import sys
import os
import pandas

import scipy.stats
from ppe import framework
from ppe import state
from ppe import dynamics

project_dir = os.path.abspath(os.path.join(os.path.join(__file__, os.pardir), os.pardir))
ppe_dir = os.path.abspath(os.path.join(project_dir, "ppe"))
sys.path.insert(0, ppe_dir)

resource_dir = os.path.abspath(os.path.join(project_dir, "resources"))
results_dir = os.path.abspath(os.path.join(project_dir, "generated_results"))
if not os.path.isdir(results_dir):
    os.mkdir(results_dir)

seed = 0
minutes_per_day = 60 * 24

demand_filepath = os.path.abspath(os.path.join(resource_dir, "demands_3_24.csv"))
demand_frame = pandas.read_csv(demand_filepath)
est_icu_demands = demand_frame['T_600'].values.ravel() * (3 / 5.6) * (1 / 3) * (1/5)


def interarrival_function(x: float) -> float:
    return 1 / est_icu_demands[int(x)]


def patient_generator():
    pid = 0
    current_time = 0
    while True:
        pid += 1
        current_time += float(scipy.stats.expon(scale=interarrival_function(current_time)).rvs(size=1)[0])
        parrival = framework.PArrivalInfo(patient=pid, status=state.PStatusImpl(require_vent=True))
        yield framework.PArrivalTime(time=current_time, parrival=parrival)


class MyLOSGenerator(dynamics.LOSAssigner):

    def __init__(self):
        self.exp_gen = scipy.stats.expon(scale=10)

    def generate_los(self, status: framework.PatientStatus) -> float:
        return float(self.exp_gen.rvs(size=1)[0])


class MyOutcomeGenerator(dynamics.OutcomeAssigner):
    def __init__(self):
        self.icu_outcome_gen = scipy.stats.bernoulli(p=0.5)
        self.noicu_outcome_gen = scipy.stats.bernoulli(p=0.05)

    def generate_icu_outcome(self, status: framework.PatientStatus) -> framework.Outcome:
        rvs = int(self.icu_outcome_gen.rvs(size=1))
        if rvs == 1:
            return framework.Outcome.LIVES
        else:
            return framework.Outcome.DIES

    def generate_noicu_outcome(self, status: framework.PatientStatus) -> framework.Outcome:
        rvs = int(self.noicu_outcome_gen.rvs(size=1))
        if rvs == 1:
            return framework.Outcome.LIVES
        else:
            return framework.Outcome.DIES


patient_state = state.PatientState()
resource_state = state.ResourceState(beds=250, vents=250)

event_outpath = os.path.abspath(os.path.join(results_dir, "sim_out_event.csv"))
patient_outpath = os.path.abspath(os.path.join(results_dir, "patient_out_event.csv"))
outcome_outpath = os.path.abspath(os.path.join(results_dir, "outcome_out_event.csv"))
with open(event_outpath, 'w') as event_file, open(patient_outpath, 'w') as patient_file, open(outcome_outpath,
                                                                                              'w') as outcome_file:
    p_gen = patient_generator()
    handler = dynamics.PatientHandler(p_gen=p_gen,
                                      p_init=patient_state, r_init=resource_state,
                                      outcome=MyOutcomeGenerator(), los=MyLOSGenerator())
    event_log = dynamics.EventLogger(event_file=event_file)
    patient_log = dynamics.PatientLogger(patient_info_file=patient_file)
    outcome_log = dynamics.OutcomeLogger(outcome_file=outcome_file)
    simulation = framework.Simulation(handlers=[handler, event_log, patient_log, outcome_log])
    first_arrival = next(p_gen)
    simulation.schedule_event(time=first_arrival.time, event_type=framework.EventType.P_ARRIVAL,
                              event_info=first_arrival.parrival)
    simulation.run_sim(maxtime=160)
