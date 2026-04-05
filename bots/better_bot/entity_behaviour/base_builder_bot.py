from cambc import Controller, Environment, Position, EntityType
from bots.better_bot.entity_behaviour.bot import Bot
from bots.better_bot.utils.constants import CONVEYORS, BotState, DeltaTypes
from bots.better_bot.utils.helper_functions import *

class BaseBuilder(Bot):
    def __init__(self, ct: Controller):        
        super().__init__(ct)

    def update_tile(self, tile, building_id, bot_id):
        if self.current_state == BotState.GOING_TO_TARGET:
            return
        
        env = self.ct.get_tile_env(tile)
        
        if get_skibidi_distance(tile, self.base_position) <= 2 and \
            get_entity(tile, self.ct) in IGNORED_BUILDINGS and \
                env == Environment.EMPTY:
            self.set_target(tile, 2, BotState.GOING_TO_TARGET)


    def build_road(self, move_pos: Position, next_pos: Position) -> bool:
        if get_skibidi_distance(move_pos, self.base_position) == 2:
            d = decide_splitter_direction(move_pos, self.base_position)
            if self.ct.can_build_splitter(move_pos, d):
                self.ct.build_splitter(move_pos, d)
        return True
    
    def run_flood_fill(self):
        return super().run_flood_fill()
    
    def reached_target(self):
        if get_skibidi_distance(self.current_target_position, self.base_position) == 2:
            d = decide_splitter_direction(self.current_target_position, self.base_position)
            if self.ct.can_build_splitter(self.current_target_position, d):
                self.ct.build_splitter(self.current_target_position, d)

        self.set_wandering()
    
    def nearest_unexplored(self):
        return self.base_position
    
    def set_wandering(self):
        self.set_target(self.ct.get_position(), 0, BotState.WANDERING)