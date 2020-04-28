import typing
import enum
import queue


@enum.unique
class Outcome(enum.Enum):
    DIES = enum.auto()
    LIVES = enum.auto()


PatientID = int
StaffID = int


class PatientStatus(typing.NamedTuple):

    def requires_vent(self) -> bool:
        raise NotImplementedError


class PArrivalInfo(typing.NamedTuple):
    patient: PatientID
    status: PatientStatus


class PArrivalTime(typing.NamedTuple):
    time: float
    parrival: PArrivalInfo


class POutcomeInfo(typing.NamedTuple):
    patient: PatientID
    outcome: Outcome


@enum.unique
class EventType(enum.Enum):
    P_ADMIT = "PAdmit"
    P_ARRIVAL = "PArrivalInfo"
    P_DECLINE = "PDecline"
    P_OUTCOME = "POutcome"
    P_DISCHARGE = "PDischarge"
    S_END = "SEnd"
    S_AVAILABLE = "SAvailable"


EventInfo = typing.Union[PArrivalInfo, PatientID, StaffID, POutcomeInfo]


class Event(typing.NamedTuple):
    time: float
    id: int
    event_type: EventType
    event_info: typing.Any

    def __lt__(self, other):
        if isinstance(other, Event):
            if self.time == other.time:
                return self.id < other.id
            else:
                return self.time < other.time
        raise NotImplementedError("Comparison not implemented.")

    def __eq__(self, other):
        if isinstance(other, Event):
            return self.time == other.time and self.id == other.id
        raise NotImplementedError("Comparison not implemented.")

    def __ne__(self, other):
        return not self.__eq__(other)

    def __le__(self, other):
        return self.__eq__(other) or self.__lt__(other)

    def __gt__(self, other):
        return not self.__le__(other)

    def __ge__(self, other):
        return not self.__lt__(other)


class Handler:

    def handle_arrival(self, sim: 'Simulation', parrival: PArrivalInfo):
        pass

    def handle_discharge(self, sim: 'Simulation', pid: PatientID):
        pass

    def handle_staff_off(self, sim: 'Simulation', sid: StaffID):
        pass

    def handle_staff_available(self, sim: 'Simulation', sid: StaffID):
        pass

    def handle_admit(self, sim: 'Simulation', pid: PatientID):
        pass

    def handle_decline(self, sim: 'Simulation', pid: PatientID):
        pass

    def handle_outcome(self, sim: 'Simulation', outcome: Outcome, pid: PatientID):
        pass


class Simulation:
    _eventq: queue.PriorityQueue
    _next_id: int
    _handlers: typing.Iterable[Handler]
    _time: float

    def __init__(self, handlers):
        self._eventq = queue.PriorityQueue()
        self._next_id = 0
        self._handlers = handlers
        self._time = 0

    def current_time(self):
        return self._time

    def schedule_event(self, time: float, event_type: EventType, event_info: EventInfo) -> None:
        event = Event(time=time, event_type=event_type, event_info=event_info, id=self._next_id)
        self._next_id += 1
        self._eventq.put_nowait(item=event)
        return

    def trigger_event(self, event_type: EventType, event_info: EventInfo) -> None:
        for h in self._handlers:
            if event_type == EventType.P_DISCHARGE:
                h.handle_discharge(sim=self, pid=event_info)
            elif event_type == EventType.P_ARRIVAL:
                h.handle_arrival(sim=self, parrival=event_info)
            elif event_type == EventType.S_END:
                h.handle_staff_off(sim=self, sid=event_info)
            elif event_type == EventType.S_AVAILABLE:
                h.handle_staff_available(sim=self, sid=event_info)
            elif event_type == EventType.P_ADMIT:
                h.handle_admit(sim=self, pid=event_info)
            elif event_type == EventType.P_OUTCOME:
                h.handle_outcome(sim=self, pid=event_info.patient, outcome=event_info.outcome)
            elif event_type == EventType.P_DECLINE:
                h.handle_decline(sim=self, pid=event_info)
            else:
                raise RuntimeError("Invalid event type", event_type)

    def next_event(self) -> typing.Optional[Event]:
        if not self._eventq.empty():
            return self._eventq.get_nowait()
        return None

    def run_sim(self, maxtime: float):
        done = False
        while not done:
            next_event = self.next_event()
            if next_event is None:
                return
            else:
                self._time = next_event.time
                if maxtime >= next_event.time:
                    self.trigger_event(event_type=next_event.event_type, event_info=next_event.event_info)
        return
