from bots.better_bot.entity_behaviour.entity_base import *
from cambc import EntityType, ResourceType
from bots.better_bot.utils.helper_functions import *
from bots.better_bot.utils.constants import *

class Launcher(EBase):
    def __init__(self, ct: Controller):
        self.base_position = None
        self.aggression_targets = []
        self.enemy_targets = []
        self.can_launch = []
        super().__init__(ct)
    
    def run_tick(self, ct: Controller):
        self.ct = ct

        self.update_map()
        if not self.base_position:
            for building_id in ct.get_nearby_buildings():
                building_entity = ct.get_entity_type(building_id)
                if building_entity == EntityType.MARKER and ct.get_team(building_id) == self.team:
                    value = ct.get_marker_value(building_id)
                    self.base_position = decode_coordinate(value)
                    break

        for bot_id in ct.get_nearby_entities(2):
            if ct.get_entity_type(bot_id) != EntityType.BUILDER_BOT:
                return

    def update_map(self):
        self.aggression_targets = []
        self.enemy_targets = []
        self.can_launch = []

        for entity_id in self.ct.get_nearby_entities():
            entity_type = self.ct.get_entity_type(entity_id)
            entity_pos = self.ct.get_position(entity_id)
            same_team = self.team == self.ct.get_team(entity_id)

            if not self.base_position:
                if entity_type == EntityType.MARKER and self.ct.get_team(entity_id) == self.team:
                    value = self.ct.get_marker_value(entity_id)
                    self.base_position = decode_coordinate(value)
            
            if entity_type == EntityType.ROAD and self.ct.is_tile_passable(entity_pos):
                self.enemy_targets.append((1, entity_pos, entity_type))

            elif entity_type in CONVEYORS:
                if same_team:
                    if self.ct.get_hp(entity_id) != self.ct.get_max_hp(entity_id):
                        self.aggression_targets.append((50, entity_pos, entity_type))
                    else:
                        if self.ct.is_tile_passable(entity_pos):
                            self.evaluate_aggressor_target(entity_pos, entity_id, None, entity_type)
            
            elif entity_type == EntityType.HARVESTER:
                self.evaluate_aggressor_target(entity_pos, entity_id, None, entity_type)

            elif entity_type == EntityType.BUILDER_BOT and entity_pos.distance_squared(self.ct.get_position()) <= 2:
                self.can_launch.append(entity_id)

    def launch_bots(self):
        def launch_enemy_bots():
            if not self.enemy_targets:
                return False
            
            self.enemy_targets.sort(lambda v, p, _: v * 1000 + self.ct.get_position().distance_squared(p) ,reverse=True)
            for _, target, _ in self.enemy_targets:
                if self.ct.can_launch():
                    pass
                    # wtf is this lol
            return False

        if not self.can_launch:
            return
        
        enemy_bots = list(filter(lambda x: self.ct.get_team(x) != self.team, self.can_launch))
        if enemy_bots and launch_enemy_bots():
            return
        
        allied_bots = list(filter(lambda x: self.ct.get_team(x) == self.team, self.can_launch))
        

    def evaluate_aggressor_target(self, tile: Position, building_id, bot_id, entity_type):
        def evaluate_harvesters():
            for d in DIRECTIONS:
                check_pos = tile.add(d)
                if not checkable_position(check_pos, self.ct):
                    continue
                b_entity = get_entity(check_pos, self.ct)
                b_id = self.ct.get_tile_building_id(check_pos)
                if b_entity in IGNORED_BUILDINGS or (b_entity == EntityType.ROAD and self.ct.get_team(b_id) == self.team):
                    self.aggression_targets.append((100, tile, entity_type))
                elif b_entity in PASSABLE and b_entity != EntityType.CORE:
                    self.aggression_targets.append((50, tile, entity_type))

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
            
            self.aggression_targets.append((eval, target_tile, entity_type))
        
        if bot_id or not building_id:
            return # Do not target ones that have a bot on them
        
        if entity_type == EntityType.HARVESTER:
            evaluate_harvesters()
        elif entity_type in CONVEYORS:
            evaluate_conveyors()