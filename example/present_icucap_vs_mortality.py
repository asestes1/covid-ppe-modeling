import os
import sys
import pandas
import ppe.implement
import matplotlib.pyplot

project_dir = os.path.abspath(os.path.join(os.path.join(__file__, os.pardir), os.pardir))
ppe_dir = os.path.abspath(os.path.join(project_dir, "ppe"))
sys.path.insert(0, ppe_dir)

results_dir = os.path.abspath(os.path.join(project_dir, "generated_results"))
sim_results_dir = os.path.abspath(os.path.join(results_dir, "sim_results"))

mortalities = []
treated_successfully = []
rates =[]
myrange = range(150, 305, 10)
trial_range = range(0, 20)
for i in myrange:
    avg_mortalities = 0.0
    avg_success = 0.0
    avg_rate = 0.0
    for j in trial_range:
        event_file = os.path.abspath(os.path.join(sim_results_dir, "event_out" + str(i) +"_"+str(j)+".csv"))
        event_frame = pandas.read_csv(event_file)
        value_counts = event_frame['event_type'].value_counts()
        trial_mortalities = value_counts[ppe.implement.EventType.P_DEATH.value]
        survivals =  value_counts[ppe.implement.EventType.P_LIVE.value]
        mortality_rate =  trial_mortalities/(trial_mortalities+survivals)
        avg_mortalities += trial_mortalities/len(trial_range)
        avg_success += survivals/len(trial_range)
        avg_rate += mortality_rate/len(trial_range)

    mortalities.append(avg_mortalities)
    treated_successfully.append(avg_success)
    rates.append(avg_rate)

y_rule = [treated_successfully[0]+ (x- myrange.start) * 0.045 * 120 for x  in myrange]

matplotlib.pyplot.figure()
matplotlib.pyplot.plot(myrange, treated_successfully, label='simulation')
matplotlib.pyplot.plot(myrange, y_rule, label="rule-of-thumb")
matplotlib.pyplot.xlabel("Beds and ventilators available")
matplotlib.pyplot.ylabel("Total Recovered")
matplotlib.pyplot.legend()
matplotlib.pyplot.savefig("total_recovered.png",bbox_inches='tight')

matplotlib.pyplot.figure()
matplotlib.pyplot.plot(myrange, mortalities)
matplotlib.pyplot.xlabel("Beds and ventilators available")
matplotlib.pyplot.ylabel("Total Mortalities")
matplotlib.pyplot.savefig("total_mortalities.png")


matplotlib.pyplot.figure()
matplotlib.pyplot.plot(myrange, rates)
matplotlib.pyplot.xlabel("Beds and ventilators available")
matplotlib.pyplot.ylabel("Mortality Rate Among Critical")
matplotlib.pyplot.savefig("mortality_rate.png")
matplotlib.pyplot.show()
