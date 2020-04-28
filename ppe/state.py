from . import framework
import typing
import warnings
import enum
import csv


@enum.unique
class CovidStatus:
    Susceptible: enum.auto()
    Infected: enum.auto()
    Recovered: enum.auto()


class PStatusImpl(framework.PatientStatus, typing.NamedTuple):
    require_vent: bool

    def requires_vent(self) -> bool:
        return self.require_vent


class PatientState:
    patients: typing.Dict[framework.PatientID, framework.PatientStatus]

    def __init__(self, patients: typing.Optional[typing.Dict[framework.PatientID, framework.PatientStatus]] = None):
        if patients is None:
            self.patients = {}
        else:
            self.patients = patients

    def get_status(self, patient: framework.PatientID) -> framework.PatientStatus:
        if patient not in self.patients:
            warnings.warn("Tried to get status of patient that does not exist")
        else:
            return self.patients[patient]

    def add_patient(self, patient: framework.PatientID, status: framework.PatientStatus):
        if patient in self.patients:
            warnings.warn("Tried to add patient with duplicate id to patient state")
        else:
            self.patients[patient] = status

    def remove_patient(self, patient: framework.PatientID):
        if patient not in self.patients:
            warnings.warn("Tried to remove patient that does not exist")
        else:
            del self.patients[patient]


class ResourceState:
    beds: int
    ventilators: int
    bed_patients: typing.Set[framework.PatientID]
    vent_patients: typing.Set[framework.PatientID]

    def __init__(self, beds: int, vents: int, bed_patients: typing.Optional[typing.Set[framework.PatientID]] = None,
                 vent_patients: typing.Optional[typing.Set[framework.PatientID]] = None):
        self.beds = beds
        self.ventilators = vents
        if bed_patients is None:
            self.bed_patients = set()
        else:
            self.bed_patients = bed_patients
        if vent_patients is None:
            self.vent_patients = set()
        else:
            self.vent_patients = vent_patients

    def bed_available(self) -> bool:
        return self.beds - len(self.bed_patients) > 0

    def vent_available(self) -> bool:
        return self.ventilators - len(self.vent_patients) > 0

    def assign_bed(self, pid: framework.PatientID) -> None:
        self.bed_patients.add(pid)

    def assign_vent(self, pid: framework.PatientID) -> None:
        self.vent_patients.add(pid)

    def remove_bed(self, pid: framework.PatientID, warn: typing.Optional[bool] = True) -> None:
        if pid in self.bed_patients:
            self.bed_patients.remove(pid)
        elif warn:
            warnings.warn("Attempted to remove patient from a bed that wasn't in a bed")

    def remove_vent(self, pid: framework.PatientID, warn: typing.Optional[bool] = True) -> None:
        if pid in self.vent_patients:
            self.vent_patients.remove(pid)
        elif warn:
            warnings.warn("Attempted to remove patient from ventilator that wasn't on ventilator")


@enum.unique
class ShiftType(enum.Enum):
    Day: enum.auto()
    Night: enum.auto()


StaffAssignment = typing.Dict[ShiftType, typing.Optional[framework.StaffID]]


class StaffForceStatus():
    _patient_to_staff: typing.Dict[framework.PatientID, StaffAssignment]
    _staff_to_patient: typing.Dict[framework.StaffID, typing.Set[framework.PatientID]]

    _shift_to_staff: typing.Dict[ShiftType, typing.Set[framework.StaffID]]
    _staff_to_shift: typing.Dict[framework.StaffID, ShiftType]
    _staff_to_eos: typing.Dict[framework.StaffID, float]

    _available_staff: typing.Set[framework.StaffID]

    _unavailable_staff: typing.Set[framework.StaffID]
    _staff_to_last_on: typing.Dict[framework.StaffID, float]

    def __init__(self, available_staff: typing.Optional[typing.Iterable[framework.StaffID]] = None):
        self._patient_to_staff = {}
        self._staff_to_patient = {}
        self._shift_to_staff = {}
        self._staff_to_shift = {}
        self._staff_to_eos = {}

        self._unavailable_staff = set()
        self._staff_to_last_on = {}

        if available_staff is not None:
            self._available_staff = set(available_staff)
        else:
            self._available_staff = set()

    def get_active_staff(self) -> typing.Set[framework.StaffID]:
        return set(self._staff_to_patient.keys())

    def get_available_staff(self) -> typing.Set[framework.StaffID]:
        return set(self._available_staff)

    def get_unavailable_staff(self) -> typing.Set[framework.StaffID]:
        return set(self._unavailable_staff)

    def unassign(self, pid: framework.PatientID, sid: framework.StaffID,
                 warn: bool = True) -> None:
        if pid in self._staff_to_patient[sid]:
            self._staff_to_patient[sid].remove(pid)
        elif warn:
            warnings.warn("Attempted to unassign a patient not assigned to a staff")

        shift_type = self._staff_to_shift[sid]
        if self._patient_to_staff[pid][shift_type] == sid:
            self._patient_to_staff[pid][shift_type] = None
        elif warn:
            warnings.warn("Attempted to unassign a staff not assigned to a patient")

    def remove_patient(self, pid: framework.PatientID, warn: bool = True) -> None:
        staff_assignment = self.get_staff(pid)
        for shift_type in ShiftType:
            sid = staff_assignment[shift_type]
            if sid is not None and pid in self._staff_to_patient[sid]:
                self._staff_to_patient[sid].remove(pid)
            else:
                if warn:
                    warnings.warn("Error in unassigning patient; staff recorded by patient did not record patient.")
        del self._patient_to_staff[pid]

    def get_patients(self, sid: framework.StaffID, warn: bool = True) -> typing.Set[framework.PatientID]:
        if sid in self._staff_to_patient:
            return self._staff_to_patient[sid]
        else:
            if warn:
                warnings.warn("Attempted to get patients for staff that is not currently active")
            return set()

    def get_staff_shift(self, sid: framework.StaffID, warn: bool = True) -> typing.Optional[ShiftType]:
        if sid in self._staff_to_shift:
            return self._staff_to_shift[sid]
        else:
            if warn:
                warnings.warn("Attempted to get shift type for staff that is not currently active")
            return None

    def get_shift_staff(self, shift_type: ShiftType):
        return self._shift_to_staff[shift_type]

    def get_eos(self, sid: framework.StaffID, warn: bool = True) -> typing.Optional[float]:
        if sid in self._staff_to_eos:
            return self._staff_to_eos[sid]
        if warn:
            warnings.warn("Error in StaffForceState.get_eos: requested EOS not available")
        return None

    def get_staff(self, pid: framework.PatientID, warn: bool = True) -> typing.Optional[StaffAssignment]:
        if pid in self._patient_to_staff:
            return dict(self._patient_to_staff[pid])
        else:
            if warn:
                warnings.warn("Attempted to get staff connected to patient that has no assigned staff.")
            return None

    def make_unavailable(self, sid: framework.StaffID, time: float, warn: bool = True) -> None:
        if sid in self._staff_to_patient:
            patients = self.get_patients(sid, warn=warn)
            for pid in patients:
                self.unassign(sid=sid, pid=pid, warn=warn)
            del self._staff_to_patient[sid]

            shift = self._staff_to_shift[sid]
            self._shift_to_staff[shift].remove(sid)

            del self._staff_to_shift[sid]
            del self._staff_to_eos[sid]

        elif sid in self._available_staff:
            self._available_staff.remove(sid)
        elif warn:
            warnings.warn("Attempted to make a staff unavailable that is neither active nor available.")

        self._staff_to_last_on[sid] = time
        self._unavailable_staff.add(sid)

    def make_available(self, sid: framework.StaffID, warn: bool = True) -> None:
        if sid in self._unavailable_staff:
            self._available_staff.add(sid)
        else:
            if warn:
                warnings.warn("Attempted to make staff available when not unavailable.")

    def start_shift(self, sid: framework.StaffID, shift_type: ShiftType, eos: float,
                    warn: bool = True) -> None:
        if sid in self._available_staff:
            self._available_staff.remove(sid)
            self._shift_to_staff[shift_type].add(sid)
            self._staff_to_shift[sid] = shift_type
            self._staff_to_patient[sid] = set()
            self._staff_to_eos[sid] = eos
        else:
            if warn:
                warnings.warn("Attempted to add staff to shift when not available.")

    def add_patient(self, pid: framework.PatientID, warn: bool = True):
        if pid in self._patient_to_staff:
            if warn:
                warnings.warn("Error in StaffForceStatus.add_patient: Attempted to add patient that already exists.")
            return

        self._patient_to_staff[pid] = {t: None for t in ShiftType}

    def assign(self, sid: framework.StaffID, pid: framework.PatientID, warn: bool = True):
        if pid not in self._patient_to_staff:
            if warn:
                warnings.warn("Attempted to assign a patient that does not exist.")
            return

        if sid in self._staff_to_shift[sid]:
            shift_type = self._staff_to_shift[sid]
            if self._patient_to_staff[pid][shift_type] is not None and warn:
                warnings.warn("Assigned staff to patient in shift that is already covered")
                previous_sid = self._patient_to_staff[pid][shift_type]
                self.unassign(pid=pid, sid=previous_sid, warn=warn)

            self._staff_to_patient[sid].add(pid)
            self._patient_to_staff[pid][shift_type] = sid
        elif warn:
            warnings.warn("Attempted to assign a patient to a staff that is not active.")

    def get_last_on(self, sid: framework.StaffID, warn: bool = True):
        return self._staff_to_last_on[sid]
