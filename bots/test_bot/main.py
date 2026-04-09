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
        seen_tiles = []
        print(ct.get_cpu_time_elapsed())
        ran = ct.get_vision_radius_sq()
        ran_root = int(ran ** 0.5)
        prntstmt = ""
        match ct.get_current_round() % 5:
            case 0:
                for tile in ct.get_nearby_tiles():
                    seen_tiles.append(tile)
                prntstmt = "nearby tiles"
            case 1:
                for tile in ct.get_nearby_entities():
                    seen_tiles.append(tile)
                prntstmt = "nearby entities"
            case 2:
                for tile in ct.get_nearby_buildings():
                    seen_tiles.append(tile)
                prntstmt = "nearby buildings"
            case 3:
                for tile in ct.get_nearby_units():
                    seen_tiles.append(tile)
                prntstmt = "nearby units"
            case 4:
                for i in range(-ran_root, ran_root + 1):
                    for j in range(-ran_root, ran_root + 1):
                        seen_tiles.append((i, j))
        print(prntstmt)
        print(ct.get_cpu_time_elapsed())

