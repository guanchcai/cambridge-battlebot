from utils.tile_info import TileData
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
        
        tile_data = self.get_from_pos(self.position)
        
        if self.ct.can_fire(self.position) and not tile_data.own_team:
            self.ct.fire(self.position)
        
        if tile_data.building_id and not tile_data.own_team:
            return False

        if (tile_data.building_type is None or tile_data.is_team_road()) and \
           self.ct.get_tile_env(self.position) not in ORE_SITES:
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

    def update_tile(self, tile: Position, tile_data: TileData | None):
        if tile_data is None: return
        if not checkable_position(tile, self.ct): return

        if tile_data.bot_id and self.ct.get_team(tile_data.bot_id) == self.team:
            return
                
        etype = tile_data.building_type
        conveyor_target = get_conveyor_target(tile, self.ct)
         
        if etype in CONVEYORS and tile_data.own_team:
            damaged = self.ct.get_hp(tile_data.building_id) != self.ct.get_max_hp(tile_data.building_id)
            if damaged:
                self.repair_targets.append((tile, 2))

            targeted_enemy_turret = False
            c_target = get_conveyor_target(tile, self.ct)
            if c_target and checkable_position(c_target, self.ct):
                turret_tile_data = self.get_from_pos(c_target)
                if turret_tile_data and turret_tile_data.building_type in TURRETS and not turret_tile_data.own_team:
                    targeted_enemy_turret = True

            if targeted_enemy_turret:
                self.repair_targets.append((tile, 0))
            elif etype != EntityType.SPLITTER and conveyor_target and checkable_position(conveyor_target, self.ct):
                conveyor_target_tile_data = self.get_from_pos(conveyor_target)
                if conveyor_target_tile_data and conveyor_target_tile_data.own_team and conveyor_target_tile_data.building_type not in VALUABLE_ENEMY_ENTITIES:
                    self.repair_targets.append((tile, 0))

            if tile not in self.visited_conveyors:
                if tile.distance_squared(self.position) <= 4:
                    self.visited_conveyors.add(tile)
                else:
                    self.visiting_queue.add(tile)
            
            if tile in self.visiting_queue and tile.distance_squared(self.position) <= 4:
                self.visiting_queue.discard(tile)
                self.visited_conveyors.add(tile)

            # valid repair target section ------------------------------------------------------------------------------------------
            is_valid_repair_target = False

            if tile == self.current_target_position and self.current_state == BotState.GOING_TO_TARGET:
                is_valid_repair_target = False

                if damaged or targeted_enemy_turret:
                    is_valid_repair_target = True

                # conveyor pointing at a valuable own-team building
                if not is_valid_repair_target and etype != EntityType.SPLITTER and conveyor_target and checkable_position(conveyor_target, self.ct):
                    conveyor_target_tile_data = self.get_from_pos(conveyor_target)
                    if conveyor_target_tile_data and conveyor_target_tile_data.own_team and \
                    conveyor_target_tile_data.building_type not in VALUABLE_ENEMY_ENTITIES:
                        is_valid_repair_target = True

                # conveyor sending stuff to enemy valuable entity
                if not is_valid_repair_target and conveyor_target and checkable_position(conveyor_target, self.ct):
                    c_target_data = self.get_from_pos(conveyor_target)
                    if c_target_data:
                        if not c_target_data.own_team and c_target_data.building_type in VALUABLE_ENEMY_ENTITIES:
                            is_valid_repair_target = True

                # don't repair if another own bot is already on it
                if tile_data.bot_id and tile_data.own_team and tile_data.bot_id != self.id:
                    is_valid_repair_target = False

                if not is_valid_repair_target:
                    self.set_wandering()

            # if tile == self.current_target_position and self.current_state == BotState.GOING_TO_TARGET:
            #     if damaged:
            #         is_valid_repair_target = True

            #     # conveyor sending stuff to enemy
            #     if not is_valid_repair_target:
            #         if conveyor_target and checkable_position(c_target, self.ct):
            #             c_target_data = self.get_from_pos(conveyor_target)
            #             if c_target_data:
            #                 if not c_target_data.own_team and c_target_data in VALUABLE_ENEMY_ENTITIES:
            #                     is_valid_repair_target = True
            #                 elif c_target_data.building_type in IGNORED_BUILDINGS or c_target_data.building_type == EntityType.ROAD:
            #                     is_valid_repair_target = True

            #     if tile_data.bot_id and tile_data.own_team and tile_data.bot_id != self.id:
            #         is_valid_repair_target = False # Not ideal TODO

            #     if not(
            #         self.ct.get_hp(tile_data.building_id) != self.ct.get_max_hp(tile_data.building_id) or \
            #         is_valid_repair_target
            #     ):
            #         self.set_wandering()

    def nearest_unexplored(self) -> Position | None:
        position = self.ct.get_position()
        if self.visiting_queue:
            return min(self.visiting_queue, key=lambda p: position.distance_squared(p))

    def reached_target(self):
        self.visited_conveyors.add(self.current_target_position)
        print("Starting repair process")
        if self.current_state == BotState.GOING_TO_TARGET:
            
            if target_data.building_type in CONVEYORS:
                conveyor_target = get_conveyor_target(self.current_target_position, self.ct)
                conveyor_target_data = self.get_from_pos(conveyor_target)
                target_data = self.get_from_pos(self.current_target_position)
                
                damaged = self.ct.get_hp(target_data.building_id) != self.ct.get_max_hp(target_data.building_id)
                if damaged and self.ct.can_heal(self.current_target_position):
                    self.ct.heal(self.current_target_position)

                if conveyor_target_data and not conveyor_target_data.own_team and conveyor_target_data.building_type in VALUABLE_ENEMY_ENTITIES:
                    if self.ct.can_destroy(self.current_target_position):
                        self.ct.destroy(self.current_target_position)

                        self.set_target(self.base_position, 1, BotState.GOING_BACK)
                elif conveyor_target_data and conveyor_target_data.building_type in IGNORED_BUILDINGS or conveyor_target_data.building_type == EntityType.ROAD:
                    self.set_target(conveyor_target, 0, BotState.GOING_TO_TARGET)
                elif not damaged:
                    self.set_wandering()
            elif self.current_target_position == self.position:
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

    def build_conveyor_chain(self, from_pos: Position, to_pos: Position):
        print("Called build conveyor chain")
        from_data = self.get_from_pos(from_pos)
        if self.ct.can_destroy(from_pos) and (from_data.destroyable() or from_data.is_team_road()):
            self.ct.destroy(from_pos)

        bridge_target_pos_choices = self.get_positions_of_entities(from_pos, 9, EntityType.SPLITTER, self.team)
        p = self.ct.get_position()
        
        if bridge_target_pos_choices:
            bridge_target_pos = random.choice(bridge_target_pos_choices)
            if self.ct.can_build_bridge(from_pos, bridge_target_pos):
                self.ct.build_bridge(from_pos, bridge_target_pos)
                self.set_wandering()
                return
        elif from_pos.distance_squared(self.base_position) <= BASE_DIST:
            if self.ct.can_build_bridge(from_pos, self.base_position):
                self.ct.build_bridge(from_pos, self.base_position)
                self.set_wandering()
                return

        print(f"Building conveyor chain from {from_pos} to {to_pos}")
        if self.position.distance_squared(from_pos) > 1:
            print("Too far away!")
            self.set_target(from_pos, 0, BotState.GOING_TO_TARGET)
            return

        same_team = from_data and from_data.own_team
        
        if same_team and from_data.building_type in CONVEYORS:
            print("Reached existing chain")
            self.set_wandering()
            return
        
        dir = from_pos.direction_to(to_pos)
        if from_pos.distance_squared(to_pos) > 1 or get_skibidi_distance(to_pos, self.base_position) == 2:
            if self.ct.can_build_bridge(from_pos, to_pos):
                self.ct.build_bridge(from_pos, to_pos)
                
                self.set_target(to_pos, 0, BotState.GOING_TO_TARGET)
        elif from_pos.distance_squared(to_pos) == 1 and self.ct.can_build_conveyor(from_pos, dir):
            if not from_data.bot_id or from_data.bot_id == self.id:
                self.ct.build_conveyor(from_pos, dir)
    
    def run_flood_fill(self):
        match self.current_state:
            case BotState.GOING_BACK:
                self.distance_map = self.path_finder.run(
                    self.position,
                    self.current_target_position,
                    True, 
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
                    True
                )