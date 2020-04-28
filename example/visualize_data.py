import os
import sys

import pandas
import numpy
import matplotlib.pyplot

project_dir = os.path.abspath(os.path.join(os.path.join(__file__, os.pardir), os.pardir))
ppe_dir = os.path.abspath(os.path.join(project_dir, "ppe"))
resource_dir = os.path.abspath(os.path.join(project_dir, "resources"))
results_dir = os.path.abspath(os.path.join(project_dir, "generated_results"))
sys.path.insert(0, ppe_dir)

event_file = os.path.join(results_dir, "sim_out_event.csv")
patient_file = os.path.join(results_dir, "patient_out_event.csv")
patient_frame = pandas.read_csv(patient_file, index_col='pid')
patient_dict = patient_frame.to_dict(orient='index')

event_frame = pandas.read_csv(event_file)

decline_events = event_frame[event_frame['event'] == 'P_DECLINE']['time'].values

icu_events = event_frame[event_frame['event'].isin(['P_DISCHARGE', 'P_ADMIT'])]


def change_in_icu(element):
    if element == 'P_DISCHARGE':
        return -1
    elif element == 'P_ADMIT':
        return 1


icu_change = icu_events['event'].apply(change_in_icu)

matplotlib.pyplot.figure()
matplotlib.pyplot.plot(decline_events, numpy.arange(1, decline_events.shape[0] + 1))
matplotlib.pyplot.ylabel("Patients denied entry to ICU")
matplotlib.pyplot.xlabel("Days from March 11th")
matplotlib.pyplot.savefig(os.path.abspath(os.path.join(results_dir, "declines.png")), bbox_inches='tight')

matplotlib.pyplot.figure()
matplotlib.pyplot.plot(icu_events['time'], numpy.cumsum(icu_change))
matplotlib.pyplot.ylabel("Patients denied entry to ICU")
matplotlib.pyplot.xlabel("Days from March 11th")
matplotlib.pyplot.savefig(os.path.abspath(os.path.join(results_dir, "in_icu.png")),
                          bbox_inches='tight')

matplotlib.pyplot.show()
