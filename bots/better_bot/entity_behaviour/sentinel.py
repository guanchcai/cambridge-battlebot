from entity_behaviour.entity_base import *
from cambc import EntityType, ResourceType
from utils.helper_functions import *
from utils.constants import *

class Sentinel(EBase):
    def __init__(self, ct: Controller):
        super().__init__(ct)
    
    def run_tick(self, ct: Controller):
        self.ct = ct
