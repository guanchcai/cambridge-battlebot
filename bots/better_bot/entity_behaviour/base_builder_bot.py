from cambc import Controller, Environment, Position, EntityType
from entity_behaviour.bot import Bot
from utils.constants import CONVEYORS, BotState, DeltaTypes
from utils.helper_functions import *

class BaseBuilder(Bot):
    def __init__(self, ct: Controller):  
        self.potential_targets = []      
        super().__init__(ct)

    def update_tile(self, tile, building_id, bot_id):
        if not self.ct.is_tile_passable(tile):
            self.set_from_pos(self.internal_map, tile, Environment.WALL)

        if self.current_state == BotState.GOING_TO_TARGET:
            print(self.current_target_position)
            return
        
        env = self.ct.get_tile_env(tile)
        del_x = abs(tile.x - self.base_position.x)
        del_y = abs(tile.y - self.base_position.y)

        entitytype = get_entity(tile, self.ct)

        if (del_x == 0 or del_y == 0) and max(del_x, del_y) == 2 and env == Environment.EMPTY:
            if self.ct.get_global_resources()[0] >= FOUNDARY_THRESHHOLD or self.ct.get_global_resources()[1] > 0:
                if entitytype != EntityType.FOUNDRY:
                    self.potential_targets.append(tile)
            elif is_team_road(tile, self.ct) or entitytype in IGNORED_BUILDINGS:
                self.potential_targets.append(tile)
        
        elif max(del_x, del_y) == 2 and env == Environment.EMPTY:
            if get_entity(tile, self.ct) in IGNORED_BUILDINGS:
                    self.potential_targets.append(tile)

    def update_map(self):
        self.potential_targets = []
        super().update_map()      
        if self.potential_targets:
            target = min(self.potential_targets, key=lambda p: self.ct.get_position().distance_squared(p))
            self.set_target(target, 2, BotState.GOING_TO_TARGET)


    def build_road(self, move_pos: Position, next_pos: Position) -> bool:
        if get_skibidi_distance(move_pos, self.base_position) == 2:
            d = decide_splitter_direction(move_pos, self.base_position)
            if self.ct.can_build_splitter(move_pos, d):
                self.ct.build_splitter(move_pos, d)
        return True
    
    def run_flood_fill(self):
        return super().run_flood_fill()
    
    def reached_target(self):
        del_x = abs(self.current_target_position.x - self.base_position.x)
        del_y = abs(self.current_target_position.y - self.base_position.y)
        if self.ct.can_destroy(self.current_target_position) and is_team_road(self.current_target_position, self.ct):
            self.ct.destroy(self.current_target_position)
        if del_x == del_y and del_x == 2:
            if self.ct.can_build_barrier(self.current_target_position):
                self.ct.build_barrier(self.current_target_position)
        elif del_x == 0 or del_y == 0:
            if self.ct.can_destroy(self.current_target_position) and get_entity(self.current_target_position, self.ct) == EntityType.LAUNCHER:
                self.ct.destroy(self.current_target_position)
            if self.ct.get_global_resources()[0] >= FOUNDARY_THRESHHOLD or self.ct.get_global_resources()[1] > 0:
                if self.ct.can_build_foundry(self.current_target_position):
                    self.ct.build_foundry(self.current_target_position)
            elif self.ct.can_build_launcher(self.current_target_position):
                self.ct.build_launcher(self.current_target_position)
        elif max(del_x, del_y) == 2:
            d = decide_splitter_direction(self.current_target_position, self.base_position)
            if self.ct.can_build_splitter(self.current_target_position, d):
                self.ct.build_splitter(self.current_target_position, d)

        self.set_wandering()
    
    def nearest_unexplored(self):
        return self.base_position
    
    def set_wandering(self):
        self.set_target(self.ct.get_position(), 0, BotState.WANDERING)