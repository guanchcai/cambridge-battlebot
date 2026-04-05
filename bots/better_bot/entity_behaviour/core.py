from bots.better_bot.entity_behaviour.entity_base import *
from cambc import Direction

class Core(EBase):
    def __init__(self, ct: Controller):
        self.spawn_queue = [Direction.EAST, Direction.CENTRE]
        super().__init__(ct)
    
    def run_tick(self, ct: Controller):
        if self.spawn_queue:
            spawn_pos = self.original_position.add(self.spawn_queue[0])
            if ct.can_spawn(spawn_pos):
                ct.spawn_builder(spawn_pos)
                self.spawn_queue.pop(0)