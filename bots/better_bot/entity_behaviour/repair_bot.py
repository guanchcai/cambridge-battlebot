from entity_behaviour.bot import Bot
from utils.constants import *
from utils.helper_functions import *
from cambc import Controller, Position, Direction, EntityType, Environment, ResourceType
import random

class Repairer(Bot):
    def __init__(self, ct: Controller):
        self.repair_targets = []
        self.visiting_queue = set()
        self.visited_conveyors = set()
        super().__init__(ct)

    def move_to_pos(self):
        position = self.ct.get_position()
        super().move_to_pos()

    def run_tick(self, ct):
        super().run_tick(ct)
        position = ct.get_position()
        for d in ALL_DIRECTIONS:
            pos = position.add(d)
            if ct.can_heal(pos):
                ct.heal(pos)
                break

    def build_road(self, move_pos: Position, next_pos: Position):
        print(f"Trying to build road at {move_pos}")
        if self.current_state != BotState.GOING_BACK:
            return super().build_road(move_pos, next_pos)

    def update_map(self):
        self.repair_targets = []
        super().update_map()
        print(self.repair_targets)
        if self.current_state == BotState.WANDERING:
            if self.repair_targets:
                target = min(self.repair_targets, key=lambda p: self.base_position.distance_squared(p[0]))
                self.set_target(target[0], target[1], BotState.GOING_TO_TARGET)

    def update_tile(self, tile: Position, building_id: int | None, bot_id: int | None):
        if building_id is None:
            return
        
        if bot_id and self.ct.get_team(bot_id) == self.ct.get_team():
            return
                
        etype = self.ct.get_entity_type(building_id)
        same_team = self.team == self.ct.get_team(building_id)
        conveyor_target = get_conveyor_target(tile, self.ct)
        if etype in CONVEYORS and same_team:
            damaged = self.ct.get_hp(building_id) != self.ct.get_max_hp(building_id)
            if damaged:
                self.repair_targets.append((tile, 2))
            elif not is_bot_nearby(tile, self.ct):
                if is_directly_connected_to_turret(tile, other_team(self.team), self.ct):
                    self.repair_targets.append((tile, 0))
                elif etype != EntityType.SPLITTER and conveyor_target and checkable_position(conveyor_target, self.ct) and get_entity(conveyor_target, self.ct) in IGNORED_BUILDINGS:
                    self.repair_targets.append((tile, 0))
                # elif is_exposed(tile, self.ct):
                #     self.repair_targets.append((tile, 0))
            if tile not in self.visited_conveyors:
                self.visiting_queue.add(tile)

            if tile == self.current_target_position and self.current_state == BotState.GOING_TO_TARGET:
                if not(
                    self.ct.get_hp(building_id) != self.ct.get_max_hp(building_id) or \
                    is_directly_connected_to_turret(tile, other_team(self.team), self.ct) or \
                    (etype != EntityType.SPLITTER and conveyor_target and checkable_position(conveyor_target, self.ct) and get_entity(conveyor_target, self.ct) in IGNORED_BUILDINGS) or \
                    is_exposed(tile, self.ct)
                ):
                    self.set_wandering()

    def nearest_unexplored(self) -> Position | None:
        position = self.ct.get_position()
        if self.visiting_queue:
            return min(self.visiting_queue, key=lambda p: position.distance_squared(p))

    def reached_target(self):
        self.visited_conveyors.add(self.current_target_position)
        if self.current_state == BotState.WANDERING:
            self.visiting_queue.discard(self.current_target_position)
            self.set_wandering()
        elif self.current_state == BotState.GOING_TO_TARGET:
            conveyor_target = get_conveyor_target(self.current_target_position, self.ct)
            building_id = self.ct.get_tile_building_id(self.current_target_position)
            etype = self.ct.get_entity_type(building_id) if building_id else None
            
            if etype in CONVEYORS:
                damaged = self.ct.get_hp(building_id) != self.ct.get_max_hp(building_id)
                if not damaged:
                    self.set_wandering()
            elif is_directly_connected_to_turret(self.current_target_position, other_team(self.team), self.ct):
                if self.ct.can_destroy(self.current_target_position):
                    self.ct.destroy(self.current_target_position)
                
                    self.set_target(self.base_position, 1, BotState.GOING_BACK)
            elif conveyor_target and checkable_position(conveyor_target, self.ct) and get_entity(conveyor_target, self.ct) in IGNORED_BUILDINGS:
                if self.ct.can_destroy(self.current_target_position):
                    self.ct.destroy(self.current_target_position)
                
                    self.set_target(self.base_position, 1, BotState.GOING_BACK)
                    
    
    def set_wandering(self):
        next_conveyor = self.nearest_unexplored()
        if next_conveyor:
            self.set_target(next_conveyor, 4, BotState.WANDERING)
        else:
            self.visited_conveyors.clear()
            self.set_target(self.base_position, 9, BotState.WANDERING)

    def run_flood_fill(self):
        print(f"Going from {self.ct.get_position()} to {self.current_target_position}")
        
        self.distance_map = self.path_finder.run(
            self.ct.get_position(),
            self.current_target_position,
            True, 
            DeltaTypes.ALL, 
            self.target_distance_squared, 
            self.target_distance_squared == 0
        )
