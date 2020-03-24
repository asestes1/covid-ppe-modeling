import enum
import typing
import csv
import warnings
import numpy
import scipy.stats
from . import framework
from .framework import PatientInfo


class PPEStock(typing.NamedTuple):
    """
    This holds the store of PPE equipment. Right now, it's just a single number, but this could easily be accomodated to
    multiple levels of equipment.
    """
    ppe_level: int

    def consume(self, ppe: framework.PPE) -> 'PPEStock':
        if ppe.FULL_PPE:
            return PPEStock(ppe_level=self.ppe_level - 1)
        else:
            return self

@enum.unique
class EventType(enum.Enum):
    P_ARRIVAL = "PatientArrival"
    P_ADMIT = "PatientAdmit"
    P_ASSIGN = "PatientAssignment"
    P_DECLINED = "PatientDeclined"
    P_REASSIGN = "PatientReassignment"
    P_LIVE = "PatientLive"
    P_DISCHARGE = "PatientDischarge"
    P_DEATH = "PatientDeath"
    P_BED = "PatientGivenBed"
    P_VENT = "PatientGivenVentilator"
    S_END = "ShiftEnd"
    S_START = "ShiftStart"
    INVALID = "INVALID"


EVENT_CSV_FIELDS = ['event_id', 'time', 'event_type', 'patient', 'staff']
PATIENT_CSV_FIELDS = ['patient_id', 'severity', 'arrival_time']


class CSVLogger(framework.HospitalLogger):
    next_event_id: int
    event_writer: csv.DictWriter
    patient_writer: typing.Optional[csv.DictWriter]

    def __init__(self, event_file, patient_file=None):
        self.next_event_id = 0
        self.event_writer = csv.DictWriter(event_file, fieldnames=EVENT_CSV_FIELDS, lineterminator='\n')
        self.event_writer.writeheader()

        if patient_file is not None:
            self.patient_writer = csv.DictWriter(patient_file, fieldnames=PATIENT_CSV_FIELDS, lineterminator='\n')
            self.patient_writer.writeheader()
        else:
            self.patient_writer = None

    def log_event(self, time: int, event_type: EventType, patient: typing.Optional[framework.PatientInfo],
                  staff: typing.Optional[framework.StaffInfo]):
        row = {'event_id': self.next_event_id, 'time': time, 'event_type': event_type.value}
        if patient is not None:
            row['patient'] = patient.pid
        else:
            row['patient'] = ''
        if staff is not None:
            row['staff'] = staff.sid
        else:
            row['staff'] = ''

        self.next_event_id += 1
        self.event_writer.writerow(rowdict=row)

    def log_patient_admitted(self, time: int, patient: PatientInfo):
        self.log_event(time=time, patient=patient, event_type=EventType.P_ADMIT, staff=None)

    def log_patient_staff_assignment(self, time: int, patient: framework.PatientInfo, staff: framework.StaffInfo):
        self.log_event(time=time, event_type=EventType.P_ASSIGN, patient=patient, staff=staff)

    def log_patient_reassignment(self, time: int, old_staff: framework.StaffInfo, new_staff: framework.StaffInfo,
                                 patient: framework.PatientInfo):
        self.log_event(time=time, event_type=EventType.P_REASSIGN, patient=patient, staff=new_staff)

    def log_patient_outcome(self, time: int, patient: framework.PatientInfo, outcome: framework.Outcome):
        if outcome == framework.Outcome.DIES:
            event = EventType.P_DEATH
        elif outcome == framework.Outcome.LIVES:
            event = EventType.P_LIVE
        else:
            event = EventType.INVALID
            warnings.warn("Invalid event occurred: patient neither died nor lived")
        self.log_event(time=time, event_type=event, patient=patient, staff=None)

    def log_shift_end(self, end_time: int, staff: framework.StaffInfo):
        self.log_event(time=end_time, event_type=EventType.S_END, patient=None, staff=staff)

    def log_start_shift(self, time: int, staff: framework.StaffInfo, options: framework.StaffOptions):
        self.log_event(time=time, event_type=EventType.S_START, patient=None, staff=staff)

    def log_patient_discharge(self, time: int, patient: framework.PatientInfo):
        self.log_event(time=time, event_type=EventType.P_DISCHARGE, patient=patient, staff=None)

    def log_patient_given_bed(self, time: int, patient: framework.PatientInfo):
        self.log_event(time=time, event_type=EventType.P_BED, patient=patient, staff=None)

    def log_patient_given_ventilator(self, time: int, patient: framework.PatientInfo):
        self.log_event(time=time, event_type=EventType.P_VENT, patient=patient, staff=None)

    def log_patient_declined(self, time: int, patient: framework.PatientInfo):
        self.log_event(time=time, event_type=EventType.P_DECLINED, patient=patient, staff=None)

    def log_patient_arrived(self, time: int, patient: framework.PatientInfo, status: framework.PatientStatus):
        if self.patient_writer is not None:
            row = {'patient_id': patient.pid, 'arrival_time': time, 'severity': status.covid_severity.name}
            self.patient_writer.writerow(rowdict=row)


class HospitalStateImpl(framework.HospitalState):


    _ppe_level: PPEStock

    _patients: typing.Dict[framework.PatientInfo, framework.PatientStatus]
    _prev_patients: typing.Set[framework.PatientInfo]

    _bedusers: typing.Set[framework.PatientInfo]
    _ventusers: typing.Set[framework.PatientInfo]

    _inactive_staff: typing.Optional[typing.Dict[framework.StaffInfo, framework.StaffStatus]]
    _active_staff: typing.Optional[typing.Dict[framework.StaffInfo, framework.StaffStatus]]
    _active_staff_options: typing.Optional[typing.Dict[framework.StaffInfo, framework.StaffOptions]]
    _staff_assignments: typing.Optional[typing.Dict[framework.StaffInfo, typing.Set[framework.PatientInfo]]]
    _patient_assignments: typing.Optional[typing.Dict[framework.PatientInfo, typing.Set[framework.StaffInfo]]]

    def __init__(self,
                 existing_patients: typing.Dict[framework.PatientInfo, framework.PatientStatus],
                 ppe_level: typing.Optional[PPEStock] = None,
                 inactive_staff: typing.Optional[typing.Dict[framework.StaffInfo, framework.StaffStatus]] = None,
                 active_staff: typing.Optional[typing.Dict[framework.StaffInfo, framework.StaffStatus]] = None,
                 active_staff_options: typing.Optional[typing.Dict[framework.StaffInfo, framework.StaffOptions]] = None,
                 existing_assignments: typing.Optional[typing.Dict[framework.StaffInfo,
                                                                   typing.Set[framework.PatientInfo]]] = None,
                 bedusers: typing.Optional[typing.Set[framework.PatientInfo]] = None,
                 ventusers: typing.Optional[typing.Set[framework.PatientInfo]] = None):
        self._ppe_level = ppe_level

        self._inactive_staff = inactive_staff
        self._active_staff = active_staff
        self._active_staff_options = active_staff_options
        self._patients = existing_patients
        self._prev_patients = set()
        self._bedusers = bedusers
        self._ventusers = ventusers

        self._staff_assignments = existing_assignments
        if existing_assignments is not None:
            self._patient_assignments: typing.Dict[framework.PatientInfo, typing.Set[framework.StaffInfo]] = {}
            for staff, patients in self._staff_assignments.items():
                for p in patients:
                    if patients not in self._patient_assignments:
                        self._patient_assignments[p] = set()
                    self._patient_assignments[p].add(staff)
        else:
            self._patient_assignments = None
        return

    def get_ppe_level(self) -> typing.Optional[PPEStock]:
        return self._ppe_level

    def get_inactive_staff(self) -> typing.Iterable[framework.StaffInfo]:
        if self._inactive_staff is None:
            return set()
        return set(self._inactive_staff.keys())

    def get_active_staff(self) -> typing.Iterable[framework.StaffInfo]:
        if self._active_staff is None:
            return set()
        return set(self._active_staff.keys())

    def get_shift_end(self, staff: framework.StaffInfo) -> int:
        if self._active_staff is not None and staff in self._active_staff:
            return self._active_staff_options[staff].shift_end
        else:
            raise RuntimeError("Attempted to get the end of shift for a staff member not currently working.")

    def get_last_shift_end(self, staff: framework.StaffInfo) -> int:
        if self._inactive_staff is not None and staff in self._inactive_staff:
            return self._inactive_staff[staff].last_shift_end
        else:
            raise RuntimeError("Attempted to get the last end of shift for a staff member currently working.")

    def discharge_patient(self, patient):
        if patient in self._patients:
            del self._patients[patient]
            for staff in self.get_staff(patient):
                self.unassign(staff, patient)

            if self._patient_assignments is not None and patient in self._patient_assignments:
                del self._patient_assignments[patient]

            self.free_bed(patient)
            self.take_off_ventilator(patient)
        else:
            raise RuntimeError("Attempted to discharge a patient that is not in the hospital.")

    def get_patients(self, staff: framework.StaffInfo):
        if self._staff_assignments is None or staff not in self._staff_assignments:
            return set()
        return set(self._staff_assignments[staff])

    def get_staff(self, patient: framework.PatientInfo):
        if self._patient_assignments is None or patient not in self._patient_assignments:
            return set()
        return set(self._patient_assignments[patient])

    def unassign(self, staff: framework.StaffInfo, patient: framework.PatientInfo):
        try:
            self._staff_assignments[staff].remove(patient)
        except KeyError:
            raise RuntimeError("Failed unassign: staff member isn't assigned to patient.")
        try:
            self._patient_assignments[patient].remove(staff)
        except KeyError:
            raise RuntimeError("Failed unassign: patient isn't assigned to staff.")
        return

    def end_shift(self, staff: framework.StaffInfo, end_time: int):
        if staff in self._staff_assignments:
            for patient in self.get_patients(staff):
                self.unassign(staff, patient)
        self._inactive_staff[staff] = self._active_staff[staff].set_last_shift_end(end_time)
        del self._active_staff[staff]

    def assign(self, staff: framework.StaffInfo, patient: framework.PatientInfo):
        if staff not in self._staff_assignments:
            self._staff_assignments[staff] = set()

        if patient not in self._patient_assignments:
            self._patient_assignments[patient] = set()

        self._staff_assignments[staff].add(patient)
        self._patient_assignments[patient].add(staff)
        return

    def start_shift(self, staff: framework.StaffInfo, options: framework.StaffOptions):
        self._active_staff[staff] = self._inactive_staff[staff]
        del self._inactive_staff[staff]
        self._ppe_level.consume(options.ppe)
        self._active_staff_options[staff] = options

    def num_patients(self, staff: framework.StaffInfo):
        return len(self._staff_assignments[staff])

    def least_busy(self) -> typing.Optional[framework.StaffInfo]:
        if self._active_staff:
            return min(self._active_staff, key=self.num_patients)
        return None

    def most_rested(self):
        if self._inactive_staff:
            return min(self._inactive_staff, key=self.get_last_shift_end)
        return None

    def add_patient(self, patient: framework.PatientInfo, status: framework.PatientStatus):
        self._patients[patient] = status

    def give_bed(self, patient):
        self._bedusers.add(patient)

    def give_ventilator(self, patient):
        self._ventusers.add(patient)

    def free_bed(self, patient):
        try:
            self._bedusers.remove(patient)
        except KeyError:
            pass
        return

    def take_off_ventilator(self, patient):
        try:
            self._ventusers.remove(patient)
        except KeyError:
            pass
        return

    def has_exited(self, patient: framework.PatientInfo) -> bool:
        return patient in self._prev_patients

    def num_vented(self) -> int:
        return len(self._ventusers)

    def num_beds_used(self) -> int:
        return len(self._bedusers)


class LeastBusyPolicy(framework.HospitalPolicy[HospitalStateImpl], typing.NamedTuple):
    max_patients: int
    shift_length: int

    def arrival_assignment(self, arrival: framework.PatientArrival,
                           hospital: HospitalStateImpl) -> typing.Optional[framework.ArrivalAssignment]:
        least_busy = hospital.least_busy()
        if least_busy is not None and hospital.num_patients(least_busy) < self.max_patients:
            return framework.ArrivalAssignment(staff=frozenset({least_busy}))
        else:
            return None

    def eos_restaff(self, time: int, orphaned_patients: typing.Set[framework.PatientInfo],
                    hospital: HospitalStateImpl) -> framework.EOSReassignment:
        mosted_rested = hospital.most_rested()
        if mosted_rested is None:
            new_assignments = {}
            excess_capacity = {staff: hospital.num_patients(staff) - self.max_patients
                               for staff in hospital.get_active_staff()
                               if hospital.num_patients(staff) < self.max_patients}
            while orphaned_patients and excess_capacity:
                next_staff = max(excess_capacity.keys(), key=excess_capacity.get)
                next_patient = orphaned_patients.pop()
                new_assignments[next_patient] = next_staff
                excess_capacity[next_staff] -= 1
            return framework.EOSReassignment(added_staff={}, new_assignments=new_assignments)

        if hospital.get_ppe_level().ppe_level > 0:
            staff_ppe = framework.PPE.FULL_PPE
        else:
            staff_ppe = framework.PPE.NO_PPE
        shift_end = time + self.shift_length
        return framework.EOSReassignment(added_staff={mosted_rested: framework.StaffOptions(ppe=staff_ppe,
                                                                                            shift_end=shift_end)},
                                         new_assignments={p: mosted_rested for p in orphaned_patients})


class FirstComeFirstServedPolicy(framework.HospitalPolicy[HospitalStateImpl], typing.NamedTuple):
    max_beds: int
    max_ventilators: int

    def arrival_assignment(self, arrival: framework.PatientArrival,
                           hospital: HospitalStateImpl) -> typing.Optional[framework.ArrivalAssignment]:
        if hospital.num_beds_used() >= self.max_beds:
            return None

        needs_ventilator = arrival.status.covid_severity == framework.InfectionSeverity.REQ_VENT
        if needs_ventilator and hospital.num_vented() >= self.max_ventilators:
            return None

        return framework.ArrivalAssignment(given_bed=True, given_ventilator=needs_ventilator)


class HospitalModelImpl(framework.HospitalModel):
    next_id: int
    last_arrival_time: float
    _random_generator: numpy.random.RandomState
    _icu_surivivalprobs: typing.Dict[framework.InfectionSeverity, float]
    _noicu_surivivalprobs: typing.Dict[framework.InfectionSeverity, float]

    _ordered_severity: typing.Tuple[
        framework.InfectionSeverity, ...]  # NOTE: severity order is arbitrary, not increasing
    _severity_pdf: typing.Tuple[float, ...]  # Same length as _ordered_severity
    _stay_dists: typing.Dict
    _interarrival_function: typing.Callable[[int], float]

    def __init__(self, icu_survivalprobs: typing.Dict[framework.InfectionSeverity, float],
                 noicu_survivalprobs: typing.Dict[framework.InfectionSeverity, float],
                 severity_dist: typing.Dict[framework.InfectionSeverity, float],
                 stay_dists: typing.Dict,
                 interarrival_function: typing.Callable[[int], float],
                 seed=None, lowest_id: int = 0,
                 start_time: int = 0):
        """

        :param icu_survivalprobs: dictionary maps severity to probability of surviving
        :param severity_dist: dictionary maps severity to probability that ICU patient has that severity
        :param stay_dists: dictionary maps severity to distribution of stay for that patient
        :param seed:
        :param lowest_id:
        :param start_time:
        """
        self.next_id = lowest_id
        self.last_arrival_time = start_time
        self._random_generator = numpy.random.RandomState(seed=seed)
        self._icu_surivivalprobs = icu_survivalprobs
        self._noicu_surivivalprobs= noicu_survivalprobs
        self._ordered_severity = tuple(severity_dist.keys())
        self._severity_pdf = tuple(severity_dist[k] for k in self._ordered_severity)
        self._stay_dists = stay_dists

        self._interarrival_function = interarrival_function

    def generate_icu_outcome(self, patient: framework.PatientInfo,
                             status: framework.PatientStatus) -> framework.Outcome:
        survivalprob = self._icu_surivivalprobs[status.covid_severity]
        random_num = self._random_generator.random(size=1)[0]
        if random_num >= survivalprob:
            return framework.Outcome.DIES
        else:
            return framework.Outcome.LIVES

    def generate_noicu_outcome(self, patient: framework.PatientInfo,
                             status: framework.PatientStatus) -> framework.Outcome:
        survivalprob = self._noicu_surivivalprobs[status.covid_severity]
        random_num = self._random_generator.random(size=1)[0]
        if random_num >= survivalprob:
            return framework.Outcome.DIES
        else:
            return framework.Outcome.LIVES

    def generate_severity(self) -> framework.InfectionSeverity:
        random_num = self._random_generator.random(size=1)[0]
        cdf = 0.0
        for next_severity, next_prob in zip(self._ordered_severity, self._severity_pdf):
            cdf += next_prob
            if cdf > random_num:
                return next_severity
        raise RuntimeError("This code shouldn't be reached; random number generation failed.")

    def generate_next_arrival(self) -> framework.PatientArrival:
        severity = self.generate_severity()
        interarrival = float(scipy.stats.expon.rvs(scale=self._interarrival_function(self.last_arrival_time), size=1,
                                                 random_state=self._random_generator)[0])
        next_arrival_time = self.last_arrival_time + interarrival
        next_patient = framework.PatientArrival(arrival_time=int(next_arrival_time),
                                                patient=framework.PatientInfo(self.next_id),
                                                status=framework.PatientStatus(covid_severity=severity))
        self.last_arrival_time = next_arrival_time
        self.next_id += 1
        return next_patient

    def generate_stay_length(self, patient: framework.PatientInfo, status: framework.PatientStatus) -> int:
        return self._stay_dists[status.covid_severity].rvs(size=1, random_state=self._random_generator)[0]
