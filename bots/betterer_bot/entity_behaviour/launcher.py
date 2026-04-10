from entity_behaviour.entity_base import *
from cambc import EntityType, ResourceType
from utils.constants import _SENTINEL
from utils.helper_functions import *
from utils.constants import *

import random

class Launcher(EBase):
    def __init__(self, ct: Controller):
        super().__init__(ct)
        self.base_position = Position(self.map_width // 2, self.map_height // 2)
        self.aggression_targets = []
        self.enemy_targets = []
        self.conveyor_ends = {}
        self.can_launch = []
        self.x_sym = True
        self.y_sym = True
        self.r_sym = True
    
    def run_tick(self, ct: Controller):
        self.ct = ct

        self.update_map()
        self.launch_bots()

    def update_map(self):
        self.aggression_targets = []
        self.enemy_targets = []
        self.can_launch = []
        self.conveyor_ends = {}

        for entity_id in self.ct.get_nearby_entities():
            entity_type = self.ct.get_entity_type(entity_id)
            entity_pos = self.ct.get_position(entity_id)
            same_team = self.team == self.ct.get_team(entity_id)

            if entity_type == EntityType.CORE and self.ct.get_team(entity_id) == self.team:
                self.base_position = entity_pos

            if entity_type == EntityType.MARKER and self.ct.get_team(entity_id) == self.team:
                value = self.ct.get_marker_value(entity_id)
                self.base_position, x_s, y_s, r_s = decode_coordinate(value)
                self.x_sym = x_s and self.x_sym
                self.y_sym = y_s and self.y_sym
                self.r_sym = r_s and self.r_sym
            
            if entity_type == EntityType.ROAD and self.ct.is_tile_passable(entity_pos):
                self.enemy_targets.append((1, entity_pos, entity_type))

            elif entity_type == EntityType.BUILDER_BOT and entity_pos.distance_squared(self.ct.get_position()) <= 2 and get_entity(entity_pos, self.ct) != EntityType.CORE:
                self.can_launch.append(entity_id)

    def launch_bots(self):
        def launch_enemy_bots():
            if not self.enemy_targets:
                return False
            enemy_pos = self.ct.get_position(random.choice(enemy_bots))
            self.enemy_targets.sort(key=lambda item: item[0] * 1000 + self.base_position.distance_squared(item[1]), reverse=True)
            print(self.enemy_targets)
            for target in self.enemy_targets:
                if self.ct.can_launch(enemy_pos, target[1]):
                    self.ct.launch(enemy_pos, target[1])
                    return True
            return False
        
        def launch_allied_bots():
            print(self.aggression_targets)
            if not self.aggression_targets:
                return False
            ally_pos = self.ct.get_position(random.choice(allied_bots))
            self.aggression_targets.sort(key=lambda item: item[0] * 1000 - self.base_position.distance_squared(item[1]), reverse=True)
            for target in self.aggression_targets:
                if self.ct.can_launch(ally_pos, target[1]):
                    self.ct.launch(ally_pos, target[1])
                    return

        if not self.can_launch:
            return
        
        enemy_bots = list(filter(lambda x: self.ct.get_team(x) != self.team, self.can_launch))
        if enemy_bots and launch_enemy_bots():
            return
        
        allied_bots = list(filter(lambda x: self.ct.get_team(x) == self.team, self.can_launch))
        # if allied_bots:
        #     launch_allied_bots()

    def get_ends(self, pos: Position) -> list[tuple[EntityType, Team] | None]:
        if not checkable_position(pos, self.ct):
            return [None] # None signifies going out of bounds

        cached = self.conveyor_ends.get(pos, _SENTINEL)
        if cached is not _SENTINEL:
            return cached
        
        self.conveyor_ends[pos] = [] # To help with looping
        building_id = self.ct.get_tile_building_id(pos)
        building_entity = self.ct.get_entity_type(building_id) if building_id else None
        if building_entity == EntityType.SPLITTER:
            d = self.ct.get_direction(building_id)
            pos1 = pos.add(d)
            pos2 = pos.add(d.rotate_left().rotate_left())
            pos3 = pos.add(d.rotate_right().rotate_right())
            self.conveyor_ends[pos] = self.get_ends(pos1) + self.get_ends(pos2) + self.get_ends(pos3)
        elif building_entity in CONVEYORS:
            self.conveyor_ends[pos] = self.get_ends(get_conveyor_target(pos, self.ct))
        elif building_entity in IGNORED_BUILDINGS or building_entity == EntityType.ROAD:
            bot_id = self.ct.get_tile_builder_bot_id(pos)
            if bot_id:
                self.conveyor_ends[pos] = [(EntityType.BUILDER_BOT, self.ct.get_team(building_id))]
            else:
                self.conveyor_ends[pos] = [(EntityType.MARKER, Team.A)]
        else:
            self.conveyor_ends[pos] = [(building_entity, self.ct.get_team(building_id))]
        
        return self.conveyor_ends[pos]
    
    
    def get_enemy_base(self) -> Position | None:
        if not self.base_position:
            return None
        
        candidates = []
        if self.x_sym:
            candidates.append(Position(self.base_position.x, self.map_height - 1 - self.base_position.y))
        if self.y_sym:
            candidates.append(Position(self.map_width - 1 - self.base_position.x, self.base_position.y))
        if self.r_sym:
            candidates.append(Position(self.map_width - 1 - self.base_position.x, self.map_height - 1 - self.base_position.y))
        
        if not candidates:
            return None
        
        avg_x = sum(p.x for p in candidates) // len(candidates)
        avg_y = sum(p.y for p in candidates) // len(candidates)
        return Position(avg_x, avg_y)