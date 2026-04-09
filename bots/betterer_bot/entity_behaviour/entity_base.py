from cambc import Controller
from abc import ABC, abstractmethod

class EBase(ABC):
    def __init__(self, ct: Controller):
        self.ct = ct
        self.original_position = ct.get_position()
        self.team = ct.get_team()
        self.map_width = ct.get_map_width()
        self.map_height = ct.get_map_height()
        self.id = ct.get_id()

    @abstractmethod
    def run_tick(self, ct: Controller):
        pass