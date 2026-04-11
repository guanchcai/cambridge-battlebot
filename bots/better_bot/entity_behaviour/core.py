from entity_behaviour.entity_base import *
from cambc import Direction, EntityType
import math

class Core(EBase):
    def __init__(self, ct: Controller):
        self.spawn_queue = [Direction.NORTH, Direction.CENTRE, Direction.WEST]
        self.spawned = 0
        super().__init__(ct)
        self.multiplier = math.floor((self.map_width * self.map_height / 2500) * 500)
        self.builder_id = None
        self.no_bot_counter = 0
    
    def run_tick(self, ct: Controller):
        bot_count = 0
        for bot in ct.get_nearby_units(8):
            if ct.get_entity_type(bot) == EntityType.BUILDER_BOT and ct.get_team(bot) == self.team:
                bot_count += 1

        if bot_count < 2 and ct.get_current_round() > 50:
            self.no_bot_counter += 1
        else:
            self.no_bot_counter = 0

        if self.no_bot_counter >= 15 and not self.spawn_queue:
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

        ti, ax = ct.get_global_resources()
        if ct.get_current_round() < 1000 and ax > 1:
            ct.convert(ax - 1)
        elif ax > ti // 3:
            ct.convert(ax - ti // 3)


        c_r = ct.get_current_round()
        
        if c_r == 100:
            self.spawn_queue.append(Direction.NORTH)

        if c_r % self.multiplier == self.multiplier - 1 and self.spawned < 10:
            self.multiplier = max(10 , self.multiplier - 20)
            self.spawn_queue.append(Direction.WEST)

        try:
            ct.get_position(self.builder_id)
        except Exception: # need to make a new builder
            self.spawn_queue.append(Direction.CENTRE)