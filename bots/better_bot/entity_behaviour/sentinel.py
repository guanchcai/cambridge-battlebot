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
        self.conveyor_ends = {}

        for tile in self.ct.get_nearby_tiles():
            if not self.ct.can_fire(tile): continue
            for end_building in self.get_ends(tile):
                if end_building[0] in TURRETS and end_building[1] == self.team:
                    continue

            build_id = self.ct.get_tile_building_id(tile)
            bot_id = self.ct.get_tile_builder_bot_id(tile)

            score = self._score_target(build_id, bot_id)
            if score < 0: continue

            if cand is None or score > cand[1]:
                cand = (tile, score)
        
        if cand is not None:
            self.ct.fire(cand[0])

    def get_ends(self, pos: Position) -> list[tuple[EntityType, Team] | None]:
        if not checkable_position(pos, self.ct):
            return [None] # None signifies going out of bounds

        end = self.conveyor_ends.get(pos)
        if end:
            return end
        
        self.conveyor_ends[pos] = [] # To help with looping
        building_id = self.ct.get_tile_building_id(pos)
        building_entity = self.ct.get_entity_type(building_id) if building_id else None
        if building_entity == EntityType.SPLITTER:
            d = self.ct.get_direction(building_id)
            pos1 = pos.add(d)
            pos2 = pos.add(d.rotate_left().rotate_left())
            pos3 = pos.add(d.rotate_right().rotate_right())
            self.conveyor_ends[pos] = self.get_ends(pos1) + self.get_ends(pos2) + self.get_ends(pos3)
        elif building_entity in CONVEYORS:
            self.conveyor_ends[pos] = self.get_ends(get_conveyor_target(pos, self.ct))
        elif building_entity in IGNORED_BUILDINGS or building_entity == EntityType.ROAD:
            bot_id = self.ct.get_tile_builder_bot_id(pos)
            if bot_id:
                self.conveyor_ends[pos] = [(EntityType.BUILDER_BOT, self.ct.get_team(building_id))]
            else:
                self.conveyor_ends[pos] = [(EntityType.MARKER, Team.A)]
        else:
            self.conveyor_ends[pos] = [(building_entity, self.ct.get_team(building_id))]
        
        return self.conveyor_ends[pos]