from . import framework
from . import state
import typing
import enum
import csv
import warnings


class OutcomeAssigner:

    def generate_icu_outcome(self, status: framework.PatientStatus) -> framework.Outcome:
        raise NotImplementedError

    def generate_noicu_outcome(self, status: framework.PatientStatus) -> framework.Outcome:
        raise NotImplementedError


class LOSAssigner:

    def generate_los(self, status: framework.PatientStatus) -> float:
        raise NotImplementedError


class AdmissionCriteria():

    def decide_admit(self, patientstatus: framework.PatientStatus) -> bool:
        raise NotImplementedError


class BedAndVentilatorCriteria(AdmissionCriteria, typing.NamedTuple):
    resource_state: state.ResourceState

    def decide_admit(self, patientstatus: framework.PatientStatus) -> bool:
        return (self.resource_state.bed_available() and
                (not patientstatus.requires_vent() or self.resource_state.vent_available()))


class PatientHandler(framework.Handler):
    _patient_generator: typing.Generator[framework.PArrivalTime, typing.Any, typing.Any]
    _patient_state: state.PatientState
    _resource_state: state.ResourceState
    _outcome_assigner: OutcomeAssigner
    _los_assigner: LOSAssigner
    _admit_criteria: AdmissionCriteria

    def __init__(self, p_gen: typing.Generator[framework.PArrivalTime, typing.Any, typing.Any],
                 p_init: state.PatientState, r_init: state.ResourceState, outcome: OutcomeAssigner,
                 los: LOSAssigner, admit_criteria: typing.Optional[AdmissionCriteria] = None):
        self._patient_generator = p_gen
        self._patient_state = p_init
        self._resource_state = r_init
        self._outcome_assigner = outcome
        self._los_assigner = los
        if admit_criteria is None:
            self._admit_criteria = BedAndVentilatorCriteria(self._resource_state)

    def handle_outcome(self, sim: framework.Simulation, outcome: framework.Outcome, pid: framework.PatientID):
        pass

    def handle_decline(self, sim: framework.Simulation, pid: framework.PatientID):
        outcome = self._outcome_assigner.generate_noicu_outcome(self._patient_state.get_status(pid))
        self._patient_state.remove_patient(pid)
        sim.trigger_event(event_type=framework.EventType.P_OUTCOME,
                          event_info=framework.POutcomeInfo(outcome=outcome, patient=pid))

    def handle_admit(self, sim: framework.Simulation, pid: framework.PatientID):
        self._resource_state.assign_bed(pid)
        self._resource_state.assign_vent(pid)
        los = self._los_assigner.generate_los(self._patient_state.get_status(pid))
        sim.schedule_event(time=sim.current_time() + los, event_type=framework.EventType.P_DISCHARGE,
                           event_info=pid)

    def handle_discharge(self, sim: framework.Simulation, pid: framework.PatientID):
        outcome = self._outcome_assigner.generate_icu_outcome(self._patient_state.get_status(pid))
        self._resource_state.remove_bed(pid, warn=True)
        self._resource_state.remove_vent(pid, warn=False)
        self._patient_state.remove_patient(pid)
        sim.trigger_event(event_type=framework.EventType.P_OUTCOME,
                          event_info=framework.POutcomeInfo(outcome=outcome, patient=pid))

    def handle_arrival(self, sim: framework.Simulation, parrival: framework.PArrivalInfo):
        self._patient_state.add_patient(patient=parrival.patient, status=parrival.status)
        if self._admit_criteria.decide_admit(patientstatus=parrival.status):
            sim.trigger_event(event_type=framework.EventType.P_ADMIT, event_info=parrival.patient)
        else:
            sim.trigger_event(event_type=framework.EventType.P_DECLINE, event_info=parrival.patient)
        next_arrival = next(self._patient_generator, None)
        if next_arrival is not None:
            sim.schedule_event(time=next_arrival.time,
                               event_type=framework.EventType.P_ARRIVAL, event_info=next_arrival.parrival)


@enum.unique
class LogEventType(enum.Enum):
    P_ARRIVE = "PatientArrive"
    P_DISCHARGE = "PatientDischarge"
    P_ADMIT = "PatientAdmit"
    P_DECLINE = "PatientDecline"


class EventLogger(framework.Handler):
    _outcome_writer: csv.DictWriter
    _event_writer: csv.DictWriter
    _patient_info_writer: csv.DictWriter

    def log_event(self, time: float, event_type: LogEventType, patient: framework.PatientID):
        row = {'time': time, 'event': event_type.name, 'pid': patient}
        self._event_writer.writerow(rowdict=row)

    def __init__(self, event_file):
        self._event_writer = csv.DictWriter(f=event_file, fieldnames=['pid', 'time', 'event'], lineterminator="\n")
        self._event_writer.writeheader()

    def handle_admit(self, sim: framework.Simulation, pid: framework.PatientID):
        self.log_event(time=sim.current_time(), event_type=LogEventType.P_ADMIT, patient=pid)

    def handle_arrival(self, sim: framework.Simulation, parrival: framework.PArrivalInfo):
        self.log_event(time=sim.current_time(), event_type=LogEventType.P_ARRIVE, patient=parrival.patient)

    def handle_discharge(self, sim: framework.Simulation, pid: framework.PatientID):
        self.log_event(time=sim.current_time(), event_type=LogEventType.P_DISCHARGE, patient=pid)

    def handle_decline(self, sim: framework.Simulation, pid: framework.PatientID):
        self.log_event(time=sim.current_time(), event_type=LogEventType.P_DECLINE, patient=pid)


class PatientLogger(framework.Handler):
    _patient_info_writer: csv.DictWriter

    def __init__(self, patient_info_file):
        self._patient_info_writer = csv.DictWriter(f=patient_info_file, fieldnames=['pid', 'time', 'needs_vent'],
                                                   lineterminator="\n")
        self._patient_info_writer.writeheader()

    def handle_arrival(self, sim: framework.Simulation, parrival: framework.PArrivalInfo):
        self._patient_info_writer.writerow({'pid': parrival.patient, 'time': sim.current_time(),
                                            'needs_vent': parrival.status.requires_vent()})


class OutcomeLogger(framework.Handler):
    _outcome_writer: csv.DictWriter

    def __init__(self, outcome_file):
        self._outcome_writer = csv.DictWriter(f=outcome_file, fieldnames=['pid', 'outcome'], lineterminator="\n")
        self._outcome_writer.writeheader()

    def handle_outcome(self, sim: framework.Simulation, outcome: framework.Outcome, pid: framework.PatientID):
        self._outcome_writer.writerow({'pid': pid, 'outcome': outcome.name})


class PatientAssigner:

    def assign_patients(self, pids: typing.Iterable[framework.PatientID]) -> typing.Dict[framework.PatientID,
                                                                                         state.StaffAssignment]:
        raise NotImplementedError()


class DefaultPatientAssigner(typing.NamedTuple, PatientAssigner):
    staff_ratio: float
    staff_state: state.StaffForceStatus
    min_time_remaining: float
    sim: framework.Simulation

    def assign_patients(self, pids: typing.Iterable[framework.PatientID]) -> typing.Dict[framework.PatientID,
                                                                                         state.StaffAssignment]:
        active_staff = self.staff_state.get_active_staff()
        available_staff = self.staff_state.get_available_staff()
        current_time = self.sim.current_time()
        to_consider = set(sid for sid in active_staff
                          if self.staff_state.get_eos(sid, warn=True) - current_time >= self.min_time_remaining)


        staff_loads = {sid: len(self.staff_state.get_patients(sid, warn=True)) for sid in to_consider }
        def get_staff_load(sid: framework.StaffID):
            return staff_loads[sid]

        assignment = {}
        for pid in pids:
            least_load = min(to_consider, key=get_staff_load)
            if least_load < self.staff_ratio:
                assignment[pid] = least_load
                staff_loads[least_load] += 1
            elif available_staff:


                longest_break = min()











class StaffHandler(framework.Handler):
    _time_on: float
    _time_off: float
    _staff_state: state.StaffForceStatus
    _patient_assigner: PatientAssigner

    def handle_assign(self, sim: framework.Simulation, assignment: typing.Dict[framework.PatientID,
                                                                               state.StaffAssignment]):
        for pid, staff in assignment.items():
            for shift_type, sid in staff:
                if staff in self._staff_state.get_active_staff():
                    eos = sim.current_time() + self._time_off
                    self._staff_state.start_shift(sid=sid, shift_type=shift_type, eos=eos, warn=True)
                    sim.schedule_event(time=eos, event_type=framework.EventType.S_END, event_info=sid)
                elif staff in self._staff_state.get_unavailable_staff():
                    warnings.warn(
                        "Illegal reassignment in StaffHandler.handle_assign: unavailable staff assigned to patient.")
                self._staff_state.assign(sid=sid, pid=pid)

    def handle_admit(self, sim: framework.Simulation, pid: framework.PatientID):
        self._staff_state.add_patient(pid, warn=True)
        self.handle_assign(sim=sim, assignment=self._patient_assigner.assign_patients(pids={pid}))

    def handle_discharge(self, sim: framework.Simulation, pid: framework.PatientID):
        self._staff_state.remove_patient(pid, warn=True)

    def handle_staff_off(self, sim: framework.Simulation, sid: framework.StaffID):
        sim.schedule_event(time=sim.current_time() + self._time_off, event_type=framework.EventType.S_AVAILABLE,
                           event_info=sid)
        patients = self._staff_state.get_patients(sid)
        self._staff_state.make_unavailable(sid=sid, time=sim.current_time())
        self.handle_assign(sim=sim, assignment=self._patient_assigner.assign_patients(pids=patients))

    def handle_staff_available(self, sim: framework.Simulation, sid: framework.StaffID):
        self._staff_state.make_available(sid, warn=True)
