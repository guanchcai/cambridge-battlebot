from entity_behaviour.entity_base import *
from cambc import EntityType, ResourceType
from utils.helper_functions import *
from utils.constants import *

class Sentinel(EBase):
    def __init__(self, ct: Controller):
        super().__init__(ct)
    
    def run_tick(self, ct: Controller):
        self.ct = ct
        self._fire_at_best_target()
    
    def _score_target(self, build_id, bot_id) -> int:
        entity_id = bot_id or build_id
        if entity_id is None: return -1

        if self.ct.get_team(entity_id) == self.ct.get_team():
            return -1

        etype = self.ct.get_entity_type(entity_id)

        if etype == EntityType.HARVESTER:
            return -1

        if build_id and bot_id:
            if self.ct.get_entity_type(build_id) == EntityType.CORE:
                return 1000
            
        if etype in set(VALUABLE_ENEMY_ENTITIES_ORDERED):
            return VALUABLE_ENEMY_ENTITIES_ORDERED.index(etype) + 5

        return 3


    def _fire_at_best_target(self):
        cand = None

        for tile in self.ct.get_nearby_tiles():
            if not self.ct.can_fire(tile): continue

            build_id = self.ct.get_tile_building_id(tile)
            bot_id = self.ct.get_tile_builder_bot_id(tile)

            score = self._score_target(build_id, bot_id)
            if score < 0: continue

            if cand is None or score > cand[1]:
                cand = (tile, score)
        
        if cand is not None:
            self.ct.fire(cand[0])