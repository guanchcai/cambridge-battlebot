from entity_behaviour.bot import Bot
from utils.constants import *
from utils.helper_functions import *
from cambc import Controller, Position, Direction, EntityType, Environment, ResourceType
import random

class Aggressor(Bot):
    def __init__(self, ct: Controller):
        self.aggression_targets = []
        self.turrets_in_range = []
        super().__init__(ct)

    def set_wandering(self):
        self.aggression_targets = []
        super().set_wandering()

    def move_to_pos(self):
        position = self.ct.get_position()
        super().move_to_pos()

    def build_road(self, move_pos: Position, next_pos: Position):
        if self.ct.can_build_road(move_pos):
            self.ct.build_road(move_pos)
        return True

    def update_map(self):
        self.aggression_targets = []
        self.turrets_in_range = []
        super().update_map()
        if self.current_state != BotState.GOING_TO_TARGET:
            if self.aggression_targets:
                self.set_target(max(self.aggression_targets), 0, BotState.GOING_TO_TARGET)

    def update_tile(self, tile: Position, building_id: int | None, bot_id: int | None):
        if building_id is None:
            return
        
        etype = self.ct.get_entity_type(building_id)
        same_team = self.team != self.ct.get_team(building_id)
        if not same_team:
            if etype in TURRETS:
                self.turrets_in_range.append((tile, etype, self.ct.get_direction(building_id)))
            elif etype == EntityType.LAUNCHER:
                self.turrets_in_range.append(tile, etype, None)
            else:
                self.evaluate_aggressor_target(tile, building_id, bot_id, etype)
                

    def nearest_unexplored(self) -> Position | None:
        return limit_to_map(
            Position(self.enemy_pos.x + random.randint(-5, 5),
                     self.enemy_pos.y + random.randint(-5, 5)),
                    self.ct
        )

    def reached_target(self):
        if self.current_state == BotState.WANDERING:
            self.set_target(self.nearest_unexplored(), 16, BotState.GOING_TO_TARGET)
            
    def evaluate_aggressor_target(self, tile: Position, building_id, bot_id, entity_type):
        def evaluate_harvesters():
            for d in DIRECTIONS:
                check_pos = tile.add(d)
                if not checkable_position(check_pos, self.ct):
                    continue
                b_entity = get_entity(check_pos, self.ct)
                b_id = self.ct.get_tile_building_id(check_pos)
                if b_entity in IGNORED_BUILDINGS or (b_entity == EntityType.ROAD and self.ct.get_team(b_id) == self.team):
                    self.aggression_targets.append((100, tile))
                elif b_entity in PASSABLE and b_entity != EntityType.CORE:
                    self.aggression_targets.append((50, tile))

            """
                50: harvesters next to a passable (conveyors for example) this can be toned back down
                100: harvesters with nothing next to them
            """
        
        def evaluate_conveyors():
            resource = self.ct.get_stored_resource(building_id)
            eval = 0
            target_tile = tile
            match resource:
                case ResourceType.REFINED_AXIONITE:
                    eval = 10
                case ResourceType.TITANIUM:
                    eval = 9
                case _:
                    return
            
            conveyor_target = get_conveyor_target(tile, self.ct)
            if conveyor_target:
                if not checkable_position(conveyor_target, self.ct):
                    eval += 2 # So it has a slight edge over things that doesn't go offscreen
                    target_tile = conveyor_target
                elif get_entity(conveyor_target, self.ct) in INVALID_CONTAINERS:
                    eval += 10
                    target_tile = conveyor_target
            
                elif is_directly_connected_to_turret(tile, other_team(self.team), self.ct):
                    eval += 5
            """
                9: titanium connecting to another conveyor belt / building
                10: refined axiomnite connecting to another conveyor belt / building
                14: titanium connecting to an enemy
                15: refined axiomnite connecting to an enemy
                19: titanium connecting to nothing
                20: refined axiomnite connecting to nothing
            """
            
            self.aggression_targets.append((eval, target_tile))
        
        if bot_id or not building_id:
            return # Do not target ones that have a bot on them
        
        if entity_type == EntityType.HARVESTER:
            evaluate_harvesters()
        elif entity_type in CONVEYORS:
            evaluate_conveyors()