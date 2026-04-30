from cambc import *
from entity_behaviour.entity_base import *
from entity_behaviour.core import Core
from entity_behaviour.bot import Bot
from entity_behaviour.launcher import Launcher
from entity_behaviour.blocker_bot import Blocker
from entity_behaviour.base_builder_bot import BaseBuilder
from entity_behaviour.aggressor_bot import Aggressor
from utils.helper_functions import get_entity
from entity_behaviour.sentinel import Sentinel
from entity_behaviour.logistics_bot import LogisticsBot
from entity_behaviour.gunner import Gunner

class Player:
    def __init__(self):
        self.entity_script: EBase = None

    def run(self, ct: Controller):
        if ct.get_current_round() > 2000:
            return
        if not self.entity_script:
           self.entity_script = self._decide_entity(ct)

        self.entity_script.run_tick(ct)

    def _decide_entity(self, ct: Controller) -> EBase:
        base_id = ct.get_tile_building_id(ct.get_position())
        base_entity = ct.get_entity_type(base_id) if base_id else None
        base_position = None 
        if base_entity == EntityType.CORE:
            base_position = ct.get_position(base_id)
        match ct.get_entity_type():
            case EntityType.CORE:
                return Core(ct)
            case EntityType.BUILDER_BOT:
                p = ct.get_position()
                if p == base_position:
                    return BaseBuilder(ct)
                if p.x == base_position.x:
                    return LogisticsBot(ct)
                return Aggressor(ct)
            case EntityType.LAUNCHER:
                return Launcher(ct)
            case EntityType.SENTINEL:
                return Sentinel(ct)
            case EntityType.GUNNER:
                return Gunner(ct)