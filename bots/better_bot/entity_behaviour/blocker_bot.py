from cambc import Controller, Environment, Position, EntityType
from entity_behaviour.bot import Bot
from utils.constants import CONVEYORS, BotState, DeltaTypes
from utils.helper_functions import *

class Blocker(Bot):
    def __init__(self, ct: Controller):        
        super().__init__(ct)

    def update_tile(self, tile, building_id, bot_id):
        can_build_barrier = tile not in self.visited_ore_sites
        
        building_entity = self.ct.get_entity_type(building_id) if building_id else None
        position = self.ct.get_position()
        if self.get_from_pos(self.environment_map, tile) in ORE_SITES:
            self.ore_sites.add(tile)
            if building_entity not in PASSABLE:
                self.visited_ore_sites.add(tile)
            if can_build_barrier:
                if self.current_state == BotState.GOING_TO_TARGET and tile.distance_squared(position) < self.current_target_position.distance_squared(position):
                    self.set_target(tile, 2, BotState.GOING_TO_TARGET)
                elif self.current_state == BotState.WANDERING:
                    self.set_target(tile, 2, BotState.GOING_TO_TARGET)

        if bot_id:
            self.set_from_pos(self.internal_map, tile, Environment.WALL)
            if self.distance_map and tile in self.distance_map:                
                self.distance_map = None

        if tile == self.current_target_position and (bot_id or building_entity not in PASSABLE):
            self.visited_ore_sites.add(self.current_target_position)
            self.set_wandering()
    def build_road(self, move_pos: Position, next_pos: Position) -> bool:
        print(f"Trying to build road at {move_pos}")
        return super().build_road(move_pos, next_pos)
    
    def run_flood_fill(self):
        return super().run_flood_fill()
    
    def reached_target(self):
        print("Reached target")
        if self.current_state == BotState.WANDERING:
            return super().reached_target()
        
        if self.ct.get_position() == self.current_target_position:
            self.set_wandering()
        
        if self.ct.can_build_barrier(self.current_target_position):
            self.ct.build_barrier(self.current_target_position)
            self.visited_ore_sites.add(self.current_target_position)
            self.set_wandering()
    
    def nearest_unexplored(self):
        unvisited_ores = self.ore_sites - self.visited_ore_sites
        if unvisited_ores:
            to_visit = min(unvisited_ores, key=lambda ore: self.ct.get_position().distance_squared(ore))
            return to_visit
        return super().nearest_unexplored()
    
    def set_wandering(self):

        next_pos = self.nearest_unexplored()
        if next_pos in self.ore_sites:
            self.set_target(next_pos, 2, BotState.GOING_TO_TARGET)

        else:
            self.set_target(next_pos, 16, BotState.WANDERING)