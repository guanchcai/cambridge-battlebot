from entity_behaviour.entity_base import *
from cambc import Direction

class Core(EBase):
    def __init__(self, ct: Controller):
        self.spawn_queue = [Direction.EAST, Direction.CENTRE, Direction.WEST]
        self.spawned = 0
        super().__init__(ct)
    
    def run_tick(self, ct: Controller):
        if self.spawn_queue:
            spawn_pos = self.original_position.add(self.spawn_queue[0])
            if ct.can_spawn(spawn_pos):
                ct.spawn_builder(spawn_pos)
                self.spawn_queue.pop(0)
                self.spawned += 1

        ti, ax = ct.get_global_resources()
        if ax > ti // 2:
            ct.convert(ax - ti // 2)

        c_r = ct.get_current_round()
        if c_r == max(self.map_width // 2, self.map_height // 2):
            self.spawn_queue.append(Direction.EAST)
        elif c_r % 100 == 99 and self.spawned <= 8:
            self.spawn_queue.append(Direction.WEST)