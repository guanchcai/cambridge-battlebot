from entity_behaviour.entity_base import *
from cambc import EntityType, ResourceType
from utils.constants import _SENTINEL
from utils.helper_functions import *
from utils.constants import *

class Gunner(EBase):
    def __init__(self, ct: Controller):
        super().__init__(ct)
    
    def run_tick(self, ct: Controller):
        def should_fire(pos):
            pos_id = ct.get_tile_builder_bot_id(pos) or ct.get_tile_building_id(pos)
            pos_team = ct.get_team(pos_id) if pos_id else None
            if pos_team and pos_team != self.team:
                return ct.get_entity_type(pos_id)

        if ct.get_ammo_amount() <= 0:
            return
        
        fire_cand = None
        for d in DIRECTIONS:
            pos_a = ct.get_position().add(d)
            pos_b = pos_a.add(d)
            pos_c = pos_b.add(d)

            target_a = should_fire(pos_a)
            target_b = None
            target_c = None
            if target_a in PASSABLE:
                target_b = should_fire(pos_b)
            
            if target_b in PASSABLE:
                target_c = should_fire(pos_b)

            if d == ct.get_direction():
                if target_c:
                    if ct.can_fire(pos_c):
                        ct.fire(pos_c)
                if target_b:
                    if ct.can_fire(pos_b):
                        ct.fire(pos_b)
                if target_a and ct.can_fire(pos_a):
                    ct.fire(pos_a)

            elif target_a or target_b or target_c:
                fire_cand = d

        
        if fire_cand and ct.can_rotate(fire_cand):
            ct.rotate(fire_cand)