from entity_behaviour.entity_base import *
from cambc import Direction

class Launcher(EBase):
    def __init__(self, ct: Controller):
        super().__init__(ct)
    
    def run_tick(self, ct: Controller):
        return