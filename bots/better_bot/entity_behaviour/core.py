from entity_behaviour.entity_base import *
from cambc import Direction
import math

class Core(EBase):
    def __init__(self, ct: Controller):
        self.spawn_queue = [Direction.EAST, Direction.CENTRE, Direction.WEST]
        self.spawned = 0
        super().__init__(ct)
        self.multiplier = math.floor((self.map_width * self.map_height / 2500) * 300)
        self.builder_id = None
    
    def run_tick(self, ct: Controller):
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
        if ax > ti // 2:
            ct.convert(ax - ti // 2)

        c_r = ct.get_current_round()
        print(self.spawned <= 5)
        if c_r == max(self.map_width // 2, self.map_height // 2):
            self.spawn_queue.append(Direction.EAST)
        elif c_r % self.multiplier == self.multiplier - 1 and self.spawned <= 5:
            self.multiplier = max(10 , self.multiplier - 20)
            self.spawn_queue.append(Direction.WEST)

        try:
            ct.get_position(self.builder_id)
        except Exception: # need to make a new builder
            self.spawn_queue.append(Direction.CENTRE)