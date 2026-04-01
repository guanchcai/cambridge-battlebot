from cambc import Controller
from abc import ABC, abstractmethod

class EBase(ABC):
    def __init__(self, ct: Controller):
        self.ct = ct
        self.original_position = ct.get_position()

    @abstractmethod
    def run_tick(self, ct: Controller):
        pass