from cambc import *
from entity_behaviour.entity_base import *
from entity_behaviour.core import Core
from entity_behaviour.bot import Bot
from entity_behaviour.gatherer_bot import Gatherer

class Player:
    def __init__(self):
        self.entity_script: EBase = None

    def run(self, ct: Controller):
        if not self.entity_script:
           self.entity_script = self._decide_entity(ct)

        self.entity_script.run_tick(ct)

    def _decide_entity(self, ct: Controller) -> EBase:
        match ct.get_entity_type():
            case EntityType.CORE:
                return Core(ct)
            case EntityType.BUILDER_BOT:
                return Gatherer(ct)