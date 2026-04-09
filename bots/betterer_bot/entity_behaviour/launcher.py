from entity_behaviour.entity_base import *
from cambc import EntityType, ResourceType
from utils.constants import _SENTINEL
from utils.helper_functions import *
from utils.constants import *

class Launcher(EBase):
    def __init__(self, ct: Controller):
        super().__init__(ct)
    
    def run_tick(self, ct: Controller):
        self.ct = ct

        self.update_map()
        self.launch_bots()

    def update_map(self):
        pass

    def launch_bots(self):
        return