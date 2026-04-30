from entity_behaviour.entity_base import *
from cambc import Direction, EntityType, ResourceType
import math

class Core(EBase):
    def __init__(self, ct: Controller):
        self.spawn_queue = [Direction.NORTH, Direction.SOUTH, Direction.CENTRE, Direction.WEST]
        self.spawned = 0
        self.aggressors_spawned = 0  # Track number of aggressors spawned
        
        super().__init__(ct)
        self.multiplier = math.floor((self.map_width * self.map_height / 2500) * 500)
        self.builder_id = None

        self.need_foundary = False
        self.has_foundary = False
        
        self.no_bot_counter = 0
    
    def run_tick(self, ct: Controller):
        bot_count = 0
        enemy_bot_count = 0
        for bot in ct.get_nearby_entities():
            same_team = ct.get_team(bot) == self.team
            if ct.get_entity_type(bot) == EntityType.BUILDER_BOT: 
                if same_team:
                    bot_count += 1
                else:
                    enemy_bot_count += 1
            if ct.get_entity_type(bot) == EntityType.SPLITTER and same_team:
                if ct.get_stored_resource(bot) == ResourceType.RAW_AXIONITE:
                    self.need_foundary = True
            
            if ct.get_entity_type(bot) == EntityType.FOUNDRY and same_team:
                self.has_foundary = True


        c_r = ct.get_current_round()
        if c_r in {min(self.map_width, self.map_height) // 2, 500, 1000, 1500}:
            self.spawn_queue.append(Direction.EAST)
        
        if c_r in {50, 200, 500, 1000, 1100, 1200, 1300, 1400, 1500}:
            self.spawn_queue.append(Direction.WEST)


        # if c_r % self.multiplier == self.multiplier - 1:
        #     self.multiplier = max(10, self.multiplier - 20)
        #     if not self.need_foundary or self.has_foundary or ct.get_global_resources()[0] >= ct.get_foundry_cost()[0] + ct.get_builder_bot_cost()[0]:
        #         if self.aggressors_spawned < 10:  # Only queue aggressor if under the limit
        #             self.spawn_queue.append(Direction.WEST)
                    

        if bot_count < 2 + enemy_bot_count and ct.get_current_round() > 100 and (not self.need_foundary or self.has_foundary or ct.get_global_resources()[0] >= ct.get_foundry_cost()[0] + ct.get_builder_bot_cost()[0]):
            self.no_bot_counter += 1
        else:
            self.no_bot_counter = 0

        if self.no_bot_counter >= min(self.map_width, self.map_height) // 2 and not self.spawn_queue:
            self.spawn_queue.append(Direction.EAST)
            self.no_bot_counter = 0

        if self.spawn_queue:
            spawn_dir = self.spawn_queue[0]
            spawn_pos = self.original_position.add(spawn_dir)
            if ct.can_spawn(spawn_pos):
                id = ct.spawn_builder(spawn_pos)
                self.spawn_queue.pop(0)
                self.spawned += 1

                if spawn_dir == Direction.CENTRE:
                    self.builder_id = id
                # elif spawn_dir == Direction.WEST:
                #     self.aggressors_spawned += 1  # Increment aggressor count on spawn

        ti, ax = ct.get_global_resources()
        if ct.get_current_round() < 1000 and ax > 1:
            ct.convert(ax - 1)

        try:
            ct.get_position(self.builder_id)
        except Exception:  # need to make a new builder
            self.spawn_queue.insert(0, Direction.CENTRE) 
