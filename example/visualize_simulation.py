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

from ppe import implement
from ppe import framework

event_file = os.path.join(resource_dir, "event_all_ventilated.csv")
patient_file = os.path.join(resource_dir, "patient_all_ventilated.csv")
patient_frame = pandas.read_csv(patient_file, index_col='patient_id')
patient_dict = patient_frame.to_dict(orient='index')

event_frame = pandas.read_csv(event_file)
last_event = max(event_frame['time'].values)

admittances = numpy.zeros(shape=last_event + 1)
exits = numpy.zeros(shape=last_event + 1)
declines = numpy.zeros(shape=last_event + 1)
ventilated = numpy.zeros(shape=last_event + 1)
ventilated_exits = numpy.zeros(shape=last_event + 1)

for _, row in event_frame.iterrows():
    event_code = row['event_type']
    if event_code == implement.EventType.P_DECLINED.value:
        declines[row['time']] += 1
    elif event_code == implement.EventType.P_DISCHARGE.value or event_code == implement.EventType.P_DEATH.value:
        exits[row['time']] += 1

        patient_id = row['patient']
        if patient_dict[patient_id]['severity'] == framework.InfectionSeverity.REQ_VENT.name:
            ventilated_exits[row['time']] += 1
    elif event_code == implement.EventType.P_ADMIT.value:
        admittances[row['time']] += 1

        patient_id = row['patient']
        if patient_dict[patient_id]['severity'] == framework.InfectionSeverity.REQ_VENT.name:
            ventilated[row['time']] += 1

cumulative_admit = numpy.cumsum(admittances)
cumulative_exits = numpy.cumsum(exits)
cumulative_declines = numpy.cumsum(declines)
cumulative_vented = numpy.cumsum(ventilated)
cumulative_vented_exits = numpy.cumsum(ventilated_exits)

num_in_icu = cumulative_admit - cumulative_exits
num_on_vent = cumulative_vented - cumulative_vented_exits

x_axis = numpy.array(range(0, last_event + 1))
x_axis = x_axis / (24 * 60)

matplotlib.pyplot.figure()
matplotlib.pyplot.plot(x_axis, num_in_icu)
matplotlib.pyplot.ylabel("Number in ICU")
matplotlib.pyplot.xlabel("Days")
matplotlib.pyplot.savefig(os.path.abspath(os.path.join(results_dir, "num_icu_fig.png")))

matplotlib.pyplot.figure()
matplotlib.pyplot.plot(x_axis, cumulative_admit, label="Admitted")
#matplotlib.pyplot.plot(x_axis, cumulative_exits, label="Discharged")
matplotlib.pyplot.plot(x_axis, cumulative_declines, label="Not Admitted")
matplotlib.pyplot.ylabel("Patients")
matplotlib.pyplot.xlabel("Days")
matplotlib.pyplot.legend()
matplotlib.pyplot.savefig(os.path.abspath(os.path.join(results_dir, "breakdown.png")))

matplotlib.pyplot.figure()
matplotlib.pyplot.plot(x_axis, num_on_vent)
matplotlib.pyplot.ylabel("On Ventilator")
matplotlib.pyplot.xlabel("Days")

matplotlib.pyplot.savefig(os.path.abspath(os.path.join(results_dir, "vent.png")))


matplotlib.pyplot.show()
