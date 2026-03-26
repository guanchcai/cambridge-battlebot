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
        self.timer = 0
        self.start_pos = None
        self.target_pos = None
        self.movement_queue = [Direction.WEST, Direction.WEST, Direction.WEST, Direction.SOUTH, Direction.SOUTH, Direction.SOUTH, None, Direction.WEST, None]
        self.placement_queue = [None, None, None, None, None, None, (EntityType.HARVESTER, Direction.SOUTH), None, (EntityType.SENTINEL, Direction.SOUTH)]

    def run(self, ct: Controller) -> None:
        return
        etype = ct.get_entity_type()
        if etype == EntityType.CORE:
            if self.num_spawned < 1:
                # if we haven't spawned 3 builder bots yet, try to spawn one on a random tile
                spawn_pos = ct.get_position().add(Direction.WEST)
                if ct.can_spawn(spawn_pos):
                    ct.spawn_builder(spawn_pos)
                    self.num_spawned += 1
        elif etype == EntityType.BUILDER_BOT:
            movement = self.movement_queue.pop(0)
            if movement:
                ct.build_road(ct.get_position().add(movement))
                ct.move(movement)
            placement = self.placement_queue.pop(0)
            if not placement: return
            match placement[0]:
                case EntityType.HARVESTER:
                    ct.build_harvester(ct.get_position().add(placement[1]))
                case EntityType.SENTINEL:
                    ct.build_sentinel(ct.get_position().add(placement[1]), Direction.NORTH)

