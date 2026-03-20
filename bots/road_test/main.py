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
        self.internal_map = None

    def run(self, ct: Controller) -> None:
        etype = ct.get_entity_type()
        if etype == EntityType.CORE:
            if self.num_spawned < 1:
                # if we haven't spawned 3 builder bots yet, try to spawn one on a random tile
                spawn_pos = ct.get_position().add(Direction.WEST)
                if ct.can_spawn(spawn_pos):
                    ct.spawn_builder(spawn_pos)
                    self.num_spawned += 1
        elif etype == EntityType.BUILDER_BOT:
            if (not self.internal_map):
                self.internal_map = [[None] * ct.get_map_height() for _ in range(ct.get_map_width())]
            
            if (not self.start_pos):
                self.start_pos = ct.get_position()

            move_dir = Direction.WEST
            move_pos = ct.get_position().add(move_dir)
            # we need to place a conveyor or road to stand on, before we can move onto a tile
            if self.timer == 2:
                ct.build_bridge(ct.get_position().add(Direction.NORTH), self.start_pos)
                self.target_pos = ct.get_position().add(Direction.NORTH) 
            if self.timer == 6:
                ct.build_bridge(ct.get_position().add(Direction.NORTH), self.target_pos)
                self.target_pos = ct.get_position().add(Direction.NORTH)
            if ct.can_build_road(move_pos):
                ct.build_road(move_pos)
                
            if ct.can_move(move_dir):
                ct.move(move_dir)
            
            self.timer += 1

