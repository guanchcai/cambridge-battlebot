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
        
        current_tile_id = self.ct.get_tile_building_id(self.position)
        same_team = current_tile_id and self.ct.get_team(current_tile_id) == self.ct.get_team()
        if self.ct.can_fire(self.position) and not same_team:
            self.ct.fire(self.position)
            
        current_tile_entity = get_entity(self.position, self.ct)
        
        if current_tile_id and not same_team:
            return False

        if (current_tile_entity is None or is_team_road(self.position, self.ct)) and self.ct.get_tile_env(self.position) not in ORE_SITES:
            self.build_conveyor_chain(self.position, move_pos)
            return False
        elif next_pos:
            self.build_conveyor_chain(move_pos, next_pos)
            
        return True

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
            if tile not in self.visited_conveyors:
                self.visiting_queue.add(tile)

            if tile == self.current_target_position and self.current_state == BotState.GOING_TO_TARGET:
                if not(
                    self.ct.get_hp(building_id) != self.ct.get_max_hp(building_id) or \
                    is_valid_repair_target(tile, self.ct)
                ):
                    self.set_wandering()

    def nearest_unexplored(self) -> Position | None:
        position = self.ct.get_position()
        if self.visiting_queue:
            return min(self.visiting_queue, key=lambda p: position.distance_squared(p))

    def reached_target(self):
        self.visited_conveyors.add(self.current_target_position)
        if self.current_state == BotState.GOING_TO_TARGET:
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
                elif conveyor_target and checkable_position(conveyor_target, self.ct) and (get_entity(conveyor_target, self.ct) in IGNORED_BUILDINGS or get_entity(conveyor_target, self.ct) == EntityType.ROAD):
                    if self.ct.can_destroy(self.current_target_position):
                        self.ct.destroy(self.current_target_position)

                        self.set_target(self.base_position, 1, BotState.GOING_BACK)
            elif etype in IGNORED_BUILDINGS or etype == EntityType.ROAD:
                self.set_target(self.base_position, 1, BotState.GOING_BACK)
        else:
            self.visiting_queue.discard(self.current_target_position)
            self.set_wandering()
                    
    
    def set_wandering(self):
        next_conveyor = self.nearest_unexplored()
        if next_conveyor:
            self.set_target(next_conveyor, 4, BotState.WANDERING)
        else:
            self.visited_conveyors.clear()
            self.set_target(self.base_position, 0, BotState.WANDERING)

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

    def build_conveyor_chain(self, from_pos: Position, to_pos: Position, connect_next=True):
        if self.ct.can_destroy(from_pos) and is_team_road(from_pos, self.ct):
            self.ct.destroy(from_pos)

        bridge_target_pos_choices = get_positions_of_entities(from_pos, self.ct, 9, EntityType.SPLITTER, self.ct.get_team())
        
        if bridge_target_pos_choices and self.ct.get_tile_env(from_pos) not in ORE_SITES:
            bridge_target_pos = random.choice(bridge_target_pos_choices)
            to_pos = bridge_target_pos
        elif from_pos.distance_squared(self.base_position) <= BASE_DIST and not bridge_target_pos_choices:
            if self.ct.can_build_bridge(from_pos, to_pos):
                self.ct.build_bridge(from_pos, to_pos)
                

        print(f"Building conveyor chain from {from_pos} to {to_pos}")
        if self.position.distance_squared(from_pos) > 1:
            print("Too far away!")
            self.set_target(from_pos, 0, BotState.GOING_TO_TARGET)
            return

        building_id = self.ct.get_tile_building_id(from_pos)
        building_type = self.ct.get_entity_type(building_id) if building_id else None
        same_team = building_id and self.ct.get_team(building_id) == self.ct.get_team()
        
        if same_team and building_type in CONVEYORS:
            return

        if from_pos.distance_squared(to_pos) > 1 or get_skibidi_distance(to_pos, self.base_position) == 2:
            if self.ct.can_build_bridge(from_pos, to_pos):
                self.ct.build_bridge(from_pos, to_pos)

                if connect_next:
                    self.set_target(to_pos, 0, BotState.GOING_TO_TARGET)
        elif from_pos.distance_squared(to_pos) == 1 and self.ct.can_build_conveyor(from_pos, from_pos.direction_to(to_pos)):
            bot_id = self.ct.get_tile_builder_bot_id(from_pos)
            if not bot_id:
                self.ct.build_conveyor(from_pos, from_pos.direction_to(to_pos))
    
    def run_flood_fill(self):
        match self.current_state:
            case BotState.GOING_BACK:
                self.distance_map = self.path_finder.run(
                    self.position,
                    self.current_target_position,
                    False, 
                    DeltaTypes.BRIDGE, 
                    0, 
                    True
                )
            case BotState.WANDERING:
                self.distance_map = self.path_finder.run(
                    self.position,
                    self.current_target_position,
                    True, 
                    DeltaTypes.ALL, 
                    self.target_distance_squared,
                    False
                )
            case BotState.GOING_TO_TARGET:
                self.distance_map = self.path_finder.run(
                    self.position,
                    self.current_target_position,
                    True, 
                    DeltaTypes.ALL, 
                    self.target_distance_squared, 
                    False
                )