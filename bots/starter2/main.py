"""Starter bot - a simple example to demonstrate usage of the Controller API.

Each unit gets its own Player instance; the engine calls run() once per round.
Use Controller.get_entity_type() to branch on what kind of unit you are.

This bot:
  - Core: spawns up to 3 builder bots on random adjacent tiles
  - Builder bot: builds a harvester on any adjacent ore tile, then moves in a
    random direction (laying a road first so the tile is passable), and places
    a marker recording the current round number
"""

import random

from cambc import Controller, Direction, EntityType, Environment, Position

# non-centre directions
DIRECTIONS = [d for d in Direction if d != Direction.CENTRE]

class Player:
    def __init__(self):
        self.num_spawned = 0 # number of builder bots spawned so far (core)
        self.forget_timer = 0
    
    def run(self, ct: Controller) -> None:
        etype = ct.get_entity_type()
        
        if etype == EntityType.CORE:
            if self.num_spawned < 10:
                # if we haven't spawned 3 builder bots yet, try to spawn one on a random tile
                spawn_pos = ct.get_position().add(random.choice(DIRECTIONS))
                if ct.can_spawn(spawn_pos):
                    ct.spawn_builder(spawn_pos)
                    self.num_spawned += 1
        elif etype == EntityType.BUILDER_BOT:
            # if we are adjacent to an ore tile, build a harvester on it
            for d in Direction:
                check_pos = ct.get_position().add(d)
                if ct.can_build_harvester(check_pos):
                    ct.build_harvester(check_pos)
                    return
            
            nearby_tiles = ct.get_nearby_tiles()
            target = None
            if (self.forget_timer > 0):
                self.forget_timer -= 1
            else: 
                for tile in nearby_tiles:
                    if ct.get_tile_env(tile) in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE] and ct.get_tile_building_id(tile) == None:
                        target = tile
                        break
                    
            target_dir = None
            if target:
                target_dir = ct.get_position().direction_to(target)
            else:
                target_dir = random.choice(DIRECTIONS)

            
            if not is_in_bounds(ct, ct.get_position().add(target_dir)):
                return
            
            direction = self._clamp_dir(ct, target_dir)
            target_pos = ct.get_position().add(direction)

            if not (target and ct.get_position().distance_squared(target) == 1) and (random.randint(0, 100) > 90):
                self.forget_timer = 20

            if ct.get_tile_env(target_pos) in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                if ct.can_build_harvester(target_pos):
                    ct.build_harvester(target_pos)
                return
            if ct.can_build_conveyor(target_pos, direction.opposite()):
                ct.build_conveyor(target_pos, direction.opposite())
            if ct.can_move(direction):
                ct.move(direction)
            

    def _clamp_dir(self, ct: Controller, d: Direction) -> Direction:
        if (d == Direction.NORTHEAST):
            target = ct.get_position().add(Direction.NORTH)
            if (not ct.is_tile_empty(target)):
                return Direction.EAST
            return Direction.NORTH
        if (d == Direction.SOUTHEAST):
            target = ct.get_position().add(Direction.SOUTH)
            if (not ct.is_tile_empty(target)):
                return Direction.EAST
            return Direction.SOUTH
        if (d == Direction.NORTHWEST):
            target = ct.get_position().add(Direction.NORTH)
            if (not ct.is_tile_empty(target)):
                return Direction.WEST
            return Direction.NORTH
        if (d == Direction.SOUTHWEST):
            target = ct.get_position().add(Direction.SOUTH)
            if (not ct.is_tile_empty(target)):
                return Direction.WEST
            return Direction.SOUTH
        return d
    
def is_in_bounds(ct: Controller, position: Position):
    return position.x in range(ct.get_map_width()) and position.y in range(ct.get_map_height())