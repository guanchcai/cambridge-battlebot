import random

from cambc import Controller, Direction, EntityType, Environment, Position

# non-centre directions
DIRECTIONS = [d for d in Direction if d != Direction.CENTRE]

class Player:
    def __init__(self):
        self.num_spawned = 0 # number of builder bots spawned so far (core)
        self.internal_map = None

    def run(self, ct: Controller) -> None:
        if (not self.internal_map):
            self.internal_map = [[None] * ct.get_map_width() for _ in range(ct.get_map_height())]
        
        etype = ct.get_entity_type()
        if etype == EntityType.CORE:
            if self.num_spawned < 1:
                # if we haven't spawned 3 builder bots yet, try to spawn one on a random tile
                spawn_pos = ct.get_position().add(random.choice(DIRECTIONS))
                if ct.can_spawn(spawn_pos):
                    ct.spawn_builder(spawn_pos)
                    self.num_spawned += 1
        elif etype == EntityType.BUILDER_BOT:
            target_pos = ct.get_position().add(Direction.EAST)

            if ct.can_build_bridge(target_pos, ct.get_position()):
                ct.can_build_bridge(target_pos, ct.get_position())
            if ct.can_move(Direction.EAST):
                ct.move(Direction.EAST)

            