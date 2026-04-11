"""
make sentinels prioritise conveyors connected to core (using ends or something) over everything make sentinel rotate
left or right (there is a function for that, and whether if its left or right can be decided on guesses to enemy base ig) 
if it is facing a harvester THIS CODE IS DECIDED IN AGGRESSOR SCRIPT BECAUSE DIRECTION IS DECIDED WHEN BUILDING AND CAN'T CHANGE AFTER
"""

from entity_behaviour.entity_base import *
from cambc import EntityType, ResourceType
from utils.constants import _SENTINEL
from utils.helper_functions import *
from utils.constants import *

class Sentinel(EBase):
    def __init__(self, ct: Controller):
        super().__init__(ct)
    
    def run_tick(self, ct: Controller):
        self.ct = ct
        self._fire_at_best_target()
    
    def _score_target(self, tile, building_id, bot_id) -> int:
        if not (building_id or bot_id): return -1

        bot_team = bot_id and self.ct.get_team(bot_id) == self.team
        builidng_team = building_id and self.ct.get_team(building_id) == self.team 
        
        if bot_team or builidng_team:
            return -1

        etype = self.ct.get_entity_type(building_id)
        if etype == EntityType.MARKER or etype == EntityType.HARVESTER:
            return -1

        if building_id and bot_id and etype == EntityType.CORE:
            return 1000
        
        if building_id and etype in CONVEYORS:
            ends = self.get_ends(tile)
            core = False
            for end in ends:
                if not end:
                    continue
                if end[0] in TURRETS and end[1] == self.team:
                    return -1
                if end[0] == EntityType.CORE and end[1] != self.team:
                    core = True

            if core and self.ct.get_stored_resource(building_id):
                return 2000

        if etype in VALUABLE_ENEMY_ENTITIES_ORDERED:
            return VALUABLE_ENEMY_ENTITIES_ORDERED.index(etype) + 5
        
        return 3
    

    def _fire_at_best_target(self):
        cand = None
        self.conveyor_ends = {}

        for tile in self.ct.get_nearby_tiles():
            if not self.ct.can_fire(tile): continue

            build_id = self.ct.get_tile_building_id(tile)
            bot_id = self.ct.get_tile_builder_bot_id(tile)

            score = self._score_target(tile, build_id, bot_id)
            if score < 0: continue

            if cand is None or score > cand[1]:
                cand = (tile, score)
        
        if cand is not None:
            self.ct.fire(cand[0])

    def get_ends(self, pos: Position) -> list[tuple[EntityType, Team] | None]:
        if not checkable_position(pos, self.ct):
            return [None] # None signifies going out of bounds

        cached = self.conveyor_ends.get(pos, _SENTINEL)
        if cached is not _SENTINEL:
            return cached
        
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