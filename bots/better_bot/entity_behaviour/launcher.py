from entity_behaviour.entity_base import *
from cambc import EntityType, ResourceType
from utils.helper_functions import *
from utils.constants import *

class Launcher(EBase):
    def __init__(self, ct: Controller):
        super().__init__(ct)
        self.base_position = Position(self.map_width // 2, self.map_height // 2)
        self.aggression_targets = []
        self.enemy_targets = []
        self.conveyor_ends = {}
        self.can_launch = []
        self.defender = (
            check_for_entity(ct.get_position(), ct, DIRECTIONS, EntityType.CONVEYOR, ct.get_team()) or \
            check_for_entity(ct.get_position(), ct, DIRECTIONS, EntityType.SPLITTER, ct.get_team()) or \
            check_for_entity(ct.get_position(), ct, DIRECTIONS, EntityType.BRIDGE, ct.get_team())
        )
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

            elif entity_type in CONVEYORS:
                if not same_team:
                    self.evaluate_aggressor_target(entity_pos, entity_id, None, entity_type)
            
            elif entity_type == EntityType.HARVESTER:
                self.evaluate_aggressor_target(entity_pos, entity_id, None, entity_type)

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
        
        if self.defender:
            return
        
        allied_bots = list(filter(lambda x: self.ct.get_team(x) == self.team, self.can_launch))
        launch_allied_bots()
        
    def evaluate_aggressor_target(self, tile: Position, building_id, bot_id, entity_type):
        def evaluate_harvesters():
            for d in CARDINAL_DIRECTIONS:
                check_pos = tile.add(d)
                if not checkable_position(check_pos, self.ct):
                    continue
                b_entity = get_entity(check_pos, self.ct)
                bot_id = self.ct.get_tile_builder_bot_id(check_pos)
                if bot_id and bot_id != self.ct.get_id():
                    continue
                if b_entity in IGNORED_BUILDINGS or b_entity == EntityType.ROAD:
                    self.aggression_targets.append((100, check_pos))
                # elif b_entity in PASSABLE and b_entity != EntityType.CORE:
                #     self.aggression_targets.append((50, check_pos))

            """
                50: harvesters next to a passable (conveyors for example) this can be toned back down
                100: harvesters with nothing next to them
            """
        
        def evaluate_conveyors():
            resource = self.ct.get_stored_resource(building_id)
            eval = 0
            target_tile = tile

            conveyor_end = self.get_ends(tile)
            if not conveyor_end:
                return
            
            for end_building in conveyor_end:
                if end_building is None:
                    return
                if end_building[1] == self.team and (end_building[0] in TURRETS or end_building[0] == EntityType.BUILDER_BOT):
                    return

            match resource:
                case ResourceType.REFINED_AXIONITE:
                    eval = 10
                case ResourceType.TITANIUM:
                    eval = 9
                case _:
                    return
            
            conveyor_target = get_conveyor_target(tile, self.ct)
            if conveyor_target and checkable_position(conveyor_target, self.ct):
                b_id = self.ct.get_tile_builder_bot_id(conveyor_target)
                if b_id is None and get_entity(conveyor_target, self.ct) in IGNORED_BUILDINGS:
                    eval += 8
                    target_tile = conveyor_target
            if is_directly_connected_to_turret(tile, other_team(self.team), self.ct):
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
        enemy_base = self.get_enemy_base()
        if entity_type == EntityType.HARVESTER:
            evaluate_harvesters()
        elif entity_type in CONVEYORS and (not enemy_base or tile.distance_squared(enemy_base) <= 13 ** 2 * (self.x_sym + self.y_sym + self.r_sym)):
            evaluate_conveyors()

    
        def evaluate_harvesters():
            for d in CARDINAL_DIRECTIONS:
                check_pos = tile.add(d)
                if not checkable_position(check_pos, self.ct):
                    continue
                b_entity = get_entity(check_pos, self.ct)
                b_id = self.ct.get_tile_building_id(check_pos)
                if b_entity in IGNORED_BUILDINGS or is_team_road(check_pos, self.ct):
                    self.aggression_targets.append((100, check_pos))
                elif b_entity in PASSABLE and b_entity != EntityType.CORE:
                    self.aggression_targets.append((50, check_pos))

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
        
        if bot_id or not building_id or self.ct.get_team(building_id) == self.team:
            return # Do not target ones that have a bot on them
        
        if entity_type == EntityType.HARVESTER:
            evaluate_harvesters()
        elif entity_type in CONVEYORS:
            evaluate_conveyors()
    
    def get_ends(self, pos: Position) -> list[tuple[EntityType, Team] | None]:
        if not checkable_position(pos, self.ct):
            return [None] # None signifies going out of bounds

        end = self.conveyor_ends.get(pos)
        if end:
            return end
        
        self.conveyor_ends[pos] = [] # To help with looping
        building_id = self.ct.get_tile_building_id(pos)
        building_entity = self.ct.get_entity_type(building_id) if building_id else None
        if building_entity == EntityType.SPLITTER:
            d = self.ct.get_direction(building_id)
            pos1 = pos.add(d)
            pos2 = pos.add(d.rotate_left().rotate_left())
            pos3 = pos.add(d.rotate_right().rotate_right())
            self.conveyor_ends[pos] = self.get_ends(pos1) + self.get_ends(pos2) + self.ends(pos3)
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