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
                if turret_tile_data and turret_tile_data.building_type in TURRETS and turret_tile_data.own_team:
                    targeted_enemy_turret = True
                # turret_id = self.ct.get_tile_building_id(c_target)
                # if turret_id:
                #     turret_type = self.ct.get_entity_type(turret_id)
                #     if turret_type in TURRETS and self.ct.get_team(turret_id) == self.team:
                #         targeted_enemy_turret = True

            if targeted_enemy_turret:
                self.repair_targets.append((tile, 0))
            elif etype != EntityType.SPLITTER and conveyor_target and checkable_position(conveyor_target, self.ct):
                conveyor_target_tile_data = self.get_from_pos(conveyor_target)
                if conveyor_target_tile_data and conveyor_target_tile_data.own_team and conveyor_target_tile_data.building_type in VALUABLE_ENEMY_ENTITIES:
                    self.repair_targets.append((tile, 0))

            if tile not in self.visited_conveyors:
                self.visiting_queue.add(tile)

            if tile == self.current_target_position and self.current_state == BotState.GOING_TO_TARGET:
                is_valid_repair_target = False

                # is damaged
                if self.ct.get_hp(tile_data.building_id) != self.ct.get_max_hp(tile_data.building_id):
                    is_valid_repair_target = True

                # conveyor pointing directly into it AND empty
                # if conveyor_target and checkable_position(conveyor_target, self.ct):
                #     conveyor_target_tile_data = self.get_from_pos(conveyor_target)
                #     if conveyor_target_tile_data.building_type in VALUABLE_ENEMY_ENTITIES and conveyor_target_tile_data.own_team:
                #         is_valid_repair_target = True
                if not is_valid_repair_target:
                    for nearby_building_id in self.ct.get_nearby_buildings(9):
                        if self.ct.get_entity_type(nearby_building_id) not in CONVEYORS:
                            continue
                        building_position = self.ct.get_position(nearby_building_id)
                        if get_conveyor_target(building_position, self.ct) == tile:
                            is_valid_repair_target = True
                            break

                # conveyor sending stuff to enemy
                if not is_valid_repair_target:
                    if conveyor_target and checkable_position(c_target, self.ct):
                        c_target_data = self.get_from_pos(conveyor_target)
                        if c_target_data and not c_target_data.own_team and c_target_data.building_type in TURRETS:
                            is_valid_repair_target = True

                if not(
                    self.ct.get_hp(tile_data.building_id) != self.ct.get_max_hp(tile_data.building_id) or \
                    is_valid_repair_target
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

    def build_conveyor_chain(self, from_pos: Position, to_pos: Position, connect_next=True):
        # if self.ct.can_destroy(from_pos) and is_team_road(from_pos, self.ct):
        #     self.ct.destroy(from_pos)

        # bridge_target_pos_choices = get_positions_of_entities(from_pos, self.ct, 9, EntityType.SPLITTER, self.ct.get_team())
        
        # if bridge_target_pos_choices and self.ct.get_tile_env(from_pos) not in ORE_SITES:
        #     bridge_target_pos = random.choice(bridge_target_pos_choices)
        #     to_pos = bridge_target_pos
        # elif from_pos.distance_squared(self.base_position) <= BASE_DIST and not bridge_target_pos_choices:
        #     if self.ct.can_build_bridge(from_pos, to_pos):
        #         self.ct.build_bridge(from_pos, to_pos)
                

        # print(f"Building conveyor chain from {from_pos} to {to_pos}")
        # if self.position.distance_squared(from_pos) > 1:
        #     print("Too far away!")
        #     self.set_target(from_pos, 0, BotState.GOING_TO_TARGET)
        #     return

        # building_id = self.ct.get_tile_building_id(from_pos)
        # building_type = self.ct.get_entity_type(building_id) if building_id else None
        # same_team = building_id and self.ct.get_team(building_id) == self.ct.get_team()
        
        # if same_team and building_type in CONVEYORS:
        #     return

        # if from_pos.distance_squared(to_pos) > 1 or get_skibidi_distance(to_pos, self.base_position) == 2:
        #     if self.ct.can_build_bridge(from_pos, to_pos):
        #         self.ct.build_bridge(from_pos, to_pos)

        #         if connect_next:
        #             self.set_target(to_pos, 0, BotState.GOING_TO_TARGET)
        # elif from_pos.distance_squared(to_pos) == 1 and self.ct.can_build_conveyor(from_pos, from_pos.direction_to(to_pos)):
        #     bot_id = self.ct.get_tile_builder_bot_id(from_pos)
        #     if not bot_id:
        #         self.ct.build_conveyor(from_pos, from_pos.direction_to(to_pos))

        from_data = self.get_from_pos(from_pos)
        if self.ct.can_destroy(from_pos) and from_data.destroyable():
            self.ct.destroy(from_pos)

        bridge_target_pos_choices = self.get_positions_of_entities(from_pos, 9, EntityType.SPLITTER, self.team)
        
        if bridge_target_pos_choices:
            bridge_target_pos = random.choice(bridge_target_pos_choices)
            if self.ct.can_build_bridge(from_pos, bridge_target_pos):
                self.ct.build_bridge(from_pos, bridge_target_pos)
                return
        elif from_pos.distance_squared(self.base_position) <= BASE_DIST:
            if self.ct.can_build_bridge(from_pos, self.base_position):
                self.ct.build_bridge(from_pos, self.base_position)
                return

        if self.position.distance_squared(from_pos) > 1:
            self.set_target(from_pos, 0, BotState.GOING_TO_TARGET)
            return
        
        dir = from_pos.direction_to(to_pos)
        if from_pos.distance_squared(to_pos) > 1 or get_skibidi_distance(to_pos, self.base_position) == 2:
            if self.ct.can_build_bridge(from_pos, to_pos):
                self.ct.build_bridge(from_pos, to_pos)
        elif from_pos.distance_squared(to_pos) == 1 and self.ct.can_build_conveyor(from_pos, dir):
            if not from_data.bot_id or from_data.bot_id == self.id:
                self.ct.build_conveyor(from_pos, dir)
    
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