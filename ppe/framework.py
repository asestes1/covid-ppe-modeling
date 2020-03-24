import typing
import enum
import simpy


@enum.unique
class Outcome(enum.Enum):
    DIES = enum.auto()
    LIVES = enum.auto()


@enum.unique
class PPE(enum.Enum):
    NO_PPE = enum.auto()
    FULL_PPE = enum.auto()


@enum.unique
class InfectionStatus(enum.Enum):
    SUSCEPTIBLE = enum.auto()
    INFECTED = enum.auto()
    RECOVERED = enum.auto()


@enum.unique
class TestStatus(enum.Enum):
    NOT_SUSPECTED = enum.auto()
    SUSPECTED = enum.auto()
    FALSE_POSITIVE = enum.auto()
    TRUE_POSITIVE = enum.auto()
    FALSE_NEGATIVE = enum.auto()
    TRUE_NEGATIVE = enum.auto()


class InfectionSeverity(enum.Enum):
    NOT_INFECTED = enum.auto()
    INCUBATING = enum.auto()
    NONASYMPTOMATIC = enum.auto()
    MODERATE = enum.auto()
    SEVERE = enum.auto()
    REQ_VENT = enum.auto()


class PatientInfo(typing.NamedTuple):
    """
    This stores information about a patient that won't change over the course of the simulation. Right now, also this
    consists of is an identifier, but could be expanded to included other things such as age/medical history
    """
    pid: int


class PatientStatus(typing.NamedTuple):
    """
    This stores information about a patient that will change over the course of the simulation.
    """
    covid_status: typing.Optional[InfectionStatus] = None
    covid_severity: typing.Optional[InfectionSeverity] = None
    test_status: typing.Optional[TestStatus] = None


class PatientArrival(typing.NamedTuple):
    arrival_time: int
    patient: PatientInfo
    status: PatientStatus


class StaffInfo(typing.NamedTuple):
    sid: int


class StaffStatus(typing.NamedTuple):
    """
    This stores features about staff that change over time and that are not directly under the control of the hospital
    """
    covid_status: InfectionStatus
    covid_severity: InfectionSeverity
    test_status: TestStatus
    last_shift_end: int

    def set_last_shift_end(self, value: int) -> 'StaffStatus':
        return StaffStatus(covid_status=self.covid_status, covid_severity=self.covid_severity,
                           test_status=self.test_status, last_shift_end=value)


class StaffOptions(typing.NamedTuple):
    """
    This stores features about staff that change over time and that are directly under the control of the hospital
    """
    ppe: typing.Optional[PPE]
    shift_end: int


class HospitalState:
    def discharge_patient(self, patient: PatientInfo):
        raise NotImplementedError

    def start_shift(self, staff: StaffInfo, options: StaffOptions):
        raise NotImplementedError

    def end_shift(self, staff: StaffInfo, end_time: int):
        raise NotImplementedError

    def assign(self, staff: StaffInfo, patient: PatientInfo):
        raise NotImplementedError

    def get_patients(self, staff: StaffInfo) -> typing.Set[PatientInfo]:
        raise NotImplementedError

    def get_active_staff(self) -> typing.Set[StaffInfo]:
        raise NotImplementedError

    def get_shift_end(self, staff: StaffInfo) -> int:
        raise NotImplementedError

    def discharge_early(self, patient: PatientInfo):
        raise NotImplementedError

    def has_exited(self, patient: PatientInfo) -> bool:
        raise NotImplementedError

    def give_ventilator(self, patient: PatientInfo):
        raise NotImplementedError

    def take_off_ventilator(self, patient: PatientInfo):
        raise NotImplementedError

    def give_bed(self, patient: PatientInfo):
        raise NotImplementedError

    def free_bed(self, patient: PatientInfo):
        raise NotImplementedError

    def add_patient(self, patient: PatientInfo, status: PatientStatus):
        raise NotImplementedError


class HospitalModel:

    def generate_icu_outcome(self, patient: PatientInfo, status: PatientStatus) -> Outcome:
        raise NotImplementedError

    def generate_noicu_outcome(self, patient: PatientInfo, status: PatientStatus) -> Outcome:
        raise NotImplementedError

    def generate_next_arrival(self) -> PatientArrival:
        raise NotImplementedError

    def generate_stay_length(self, patient: PatientInfo, status: PatientStatus) -> int:
        raise NotImplementedError

    def staff_to_patient_transmission(self, patient: PatientInfo, patient_status: PatientStatus,
                                      staff_info: StaffInfo, staff_status: StaffStatus, interaction_duration: int):
        raise NotImplementedError


class EOSReassignment(typing.NamedTuple):
    """
    This represents the reassignment of patients to staff at the end of a shift.
    """
    added_staff: typing.Dict[StaffInfo, StaffOptions]
    new_assignments: typing.Dict[PatientInfo, typing.Set[StaffInfo]]


T = typing.TypeVar('T', bound=HospitalState, covariant=True)


class ArrivalAssignment(typing.NamedTuple):
    staff: typing.Optional[typing.FrozenSet[StaffInfo]] = None
    given_bed: typing.Optional[bool] = None
    given_ventilator: typing.Optional[bool] = None


class HospitalPolicy(typing.Generic[T]):

    def arrival_assignment(self, arrival: PatientArrival, hospital: T) -> typing.Optional[ArrivalAssignment]:
        """
        This should be called when a patient arrives in the hospital and needs to be assigned to staff members.
        :param arrival: The arriving patient
        :param hospital: The HospitalState object
        :return: the assigned staff members.
        """
        # return of None indicates patient is denied admission.
        raise NotImplementedError()

    def eos_restaff(self, time: int, orphaned_patients: typing.Set[PatientInfo],
                    hospital: T) -> EOSReassignment:
        """
        NOTE: This currently assumes that only the orphaned_patients are reassigned. If that assumption is violated,
        then need to fix handle_eos

        This should be called when a staff member finishes a shift. This decides whether to bring in more staff members
        and who to reassign patients to. This also makes decisions wrt PPE and shift length of incoming staff

        :param orphaned_patients: patients that the staff member was taking care of
        :param hospital: The HospitalState object
        :return: the new assignment
        """
        raise NotImplemented


class HospitalLogger:

    def log_patient_arrived(self, time: int, patient: PatientInfo, status: PatientStatus):
        pass

    def log_patient_staff_assignment(self, time: int, patient: PatientInfo, staff: StaffInfo):
        pass

    def log_patient_outcome(self, time: int, patient: PatientInfo, outcome: Outcome):
        pass

    def log_shift_end(self, end_time: int, staff: StaffInfo):
        pass

    def log_patient_reassignment(self, time: int, old_staff: StaffInfo, new_staff: StaffInfo, patient: PatientInfo):
        pass

    def log_start_shift(self, time: int, staff: StaffInfo, options: StaffOptions):
        pass

    def log_patient_discharge(self, time: int, patient: PatientInfo):
        pass

    def log_patient_declined(self, time: int, patient: PatientInfo):
        pass

    def log_patient_admitted(self, time: int, patient: PatientInfo):
        pass

    def log_patient_given_bed(self, time: int, patient: PatientInfo):
        pass

    def log_patient_given_ventilator(self, time: int, patient: PatientInfo):
        pass

    def log_patient_freed_bed(self, time: int, patient: PatientInfo):
        pass

    def log_patient_freed_ventilator(self, time: int, patient: PatientInfo):
        pass


def handle_patient_exit(env: simpy.Environment, exit_time: int, patient: PatientInfo, outcome: Outcome,
                        hospital: T, logger: HospitalLogger):
    current_time = env.now
    yield env.timeout(exit_time - current_time)
    if not hospital.has_exited(patient):
        if outcome == Outcome.LIVES:
            logger.log_patient_discharge(time=exit_time, patient=patient)
        logger.log_patient_outcome(time=exit_time, patient=patient, outcome=outcome)
        hospital.discharge_patient(patient)


def handle_staff_staff_interaction():
    # TODO: implement this
    yield


def handle_staff_patient_interaction():
    # TODO: implement this
    yield


def handle_patient_arrival(env: simpy.Environment, arrival: PatientArrival, hospital: T,
                           policy: HospitalPolicy[T], logger: HospitalLogger, model: HospitalModel):
    current_time = env.now
    yield env.timeout(arrival.arrival_time - current_time)

    arrival_assign = policy.arrival_assignment(arrival=arrival, hospital=hospital)
    logger.log_patient_arrived(time=arrival.arrival_time, patient=arrival.patient, status=arrival.status)
    if arrival_assign is None:
        logger.log_patient_declined(time=arrival.arrival_time, patient=arrival.patient)
        exit_outcome = model.generate_noicu_outcome(patient=arrival.patient, status=arrival.status)
        logger.log_patient_outcome(time=arrival.arrival_time, patient=arrival.patient, outcome=exit_outcome)

    else:
        exit_time = arrival.arrival_time + model.generate_stay_length(patient=arrival.patient, status=arrival.status)
        exit_outcome = model.generate_icu_outcome(patient=arrival.patient, status=arrival.status)
        env.process(handle_patient_exit(env=env, exit_time=exit_time, outcome=exit_outcome, patient=arrival.patient,
                                        hospital=hospital, logger=logger))
        hospital.add_patient(patient=arrival.patient, status=arrival.status)
        logger.log_patient_admitted(time=arrival.arrival_time, patient=arrival.patient)
        if arrival_assign.given_bed:
            hospital.give_bed(patient=arrival.patient)
            logger.log_patient_given_bed(time=arrival.arrival_time, patient=arrival.patient)

        if arrival_assign.given_ventilator:
            hospital.give_ventilator(patient=arrival.patient)
            logger.log_patient_given_ventilator(time=arrival.arrival_time, patient=arrival.patient)

        if arrival_assign.staff is not None:
            for staff in arrival_assign.staff:
                env.process(handle_staff_patient_interaction())
                logger.log_patient_staff_assignment(time=arrival.arrival_time, patient=arrival.patient, staff=staff)

    env.process(handle_patient_arrival(env=env, arrival=model.generate_next_arrival(), hospital=hospital, policy=policy,
                                       logger=logger, model=model))
    return


def apply_reassignment(time: int, orphaned_patients: typing.Set[PatientInfo],
                       staff: StaffInfo, reassignment: EOSReassignment, hospital: T,
                       logger: HospitalLogger):
    """
    #TODO: This probably needs refactoring.
    This currently assumes that the reassignment only changes assignments for orphaned patients.
    """
    for new_staff, options in reassignment.added_staff.items():
        hospital.start_shift(new_staff, options)
        logger.log_start_shift(time=time, staff=new_staff, options=options)

    for patient in orphaned_patients:
        if patient in reassignment.new_assignments and reassignment.new_assignments[patient]:
            new_staff = reassignment.new_assignments[patient]
            if new_staff:
                for s in new_staff:
                    hospital.assign(s, patient)
                    logger.log_patient_reassignment(time=time, old_staff=staff, new_staff=s, patient=patient)
        else:
            pass
            #TODO implement this
    return


def handle_eos(env: simpy.Environment, shift_end_time: int, staff: StaffInfo, hospital: T,
               logger: HospitalLogger, policy: HospitalPolicy[T],
               model: HospitalModel):
    # TODO: This probably needs refactoring.
    current_time = env.now
    yield env.timeout(shift_end_time - current_time)
    logger.log_shift_end(end_time=shift_end_time, staff=staff)
    orphaned_patients = hospital.get_patients(staff)
    hospital.end_shift(staff, end_time=shift_end_time)
    reassignment = policy.eos_restaff(shift_end_time, orphaned_patients, hospital)
    apply_reassignment(time=shift_end_time, orphaned_patients=orphaned_patients, staff=staff,
                       reassignment=reassignment, hospital=hospital, logger=logger)

    for new_staff in reassignment.added_staff:
        for active_staff in hospital.get_active_staff():
            if new_staff != active_staff:
                env.process(handle_staff_staff_interaction())
        env.process(handle_eos(env=env, shift_end_time=hospital.get_shift_end(new_staff), staff=new_staff,
                               hospital=hospital, logger=logger, policy=policy, model=model))

    for new_staff, patients in reassignment.new_assignments.items():
        for patient in patients:
            env.process(handle_staff_patient_interaction())


def icu_process(env: simpy.Environment,
                hospital_state: T,
                logger: HospitalLogger,
                policy: HospitalPolicy[T],
                model: HospitalModel):
    for staff in hospital_state.get_active_staff():
        env.process(handle_eos(env=env, shift_end_time=hospital_state.get_shift_end(staff),
                               staff=staff,
                               hospital=hospital_state, logger=logger, policy=policy,
                               model=model))

    try:
        first_arrival = model.generate_next_arrival()
        env.process(handle_patient_arrival(env=env, arrival=first_arrival, hospital=hospital_state, logger=logger,
                                           policy=policy, model=model))
    except StopIteration:
        yield
