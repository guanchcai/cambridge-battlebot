from entity_behaviour.bot import Bot
from utils.constants import *
from utils.helper_functions import *
from cambc import Controller, Position, Direction, EntityType, Environment, ResourceType
import random
from itertools import product

class Aggressor(Bot):
    def __init__(self, ct: Controller):
        self.aggression_targets = []
        self.turrets_in_range = []

        self.own_launcher_pos = None
        self.enemy_launchers = set()
        self.rounds_without_launch = 0
        super().__init__(ct)

    def set_wandering(self):
        self.aggression_targets = []
        super().set_wandering()

    # def move_to_pos(self):
    #     position = self.ct.get_position()
    #     super().move_to_pos()
    def run_tick(self, ct):
        p = ct.get_position()
        b_id = ct.get_tile_building_id(p)
        if self.own_launcher_pos:
            if ct.can_fire(p) and ct.get_team(b_id) != ct.get_team():
                ct.fire(p)
                
        return super().run_tick(ct)

    def build_road(self, move_pos: Position, next_pos: Position):
        print(f"Trying to build road at {move_pos}")
        if self.ct.can_build_road(move_pos):
            self.ct.build_road(move_pos)
        return True
    
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

    def update_map(self):
        self.aggression_targets = []
        self.turrets_in_range = []
        self.enemy_launchers = set()
        super().update_map()

        # Store all the bot launchers of enemies as a set
        # Loop through the set and set all positions nearby as walls using set_from_pos (or you can alternatively set it as update tile detects if it is a launcher)
        # If path finder can't find a path (Returns None) yet there is a target (current_target_position is not None) then:
        # Place a launcher (if possible) - if not then... uhh
        # Set target to the launcher
        # In launcher script, identify the target using the same logic (thus it should identify the same target as the bot, if not its fine as it is still "a" target)
        # Launch set bot to the target
        
        # Add if you have time:
        # If the launcher doesn't launch myself for more than 3 rounds in a row (meaning there is not targets nearby), destroy the launcher
        # This is because we blindly path find to a bot launcher trusting that it has a target

        # 1: Loop through enemy launchers and mark nearby tiles as walls
        for launcher_pos in self.enemy_launchers:
            for dx, dy in product(range(-3, 4), repeat=2):
                if dx * dx + dy * dy <= TURRET_THREAT_RADIUS:
                    wall_pos = Position(launcher_pos.x + dx, launcher_pos.y + dy)
                    if is_in_bound(wall_pos, self.ct):
                        self.set_from_pos(self.internal_map, wall_pos, Environment.WALL)
            self.distance_map = None

        # 2: Pick best target if not already hunting
        if self.current_state != BotState.GOING_TO_TARGET:
            if self.aggression_targets:
                _, best_target = max(self.aggression_targets)
                self.set_target(best_target, 0, BotState.GOING_TO_TARGET)

    def update_tile(self, tile: Position, building_id: int | None, bot_id: int | None):
        if building_id is None:
            return
        
        etype = self.ct.get_entity_type(building_id)
        same_team = self.team == self.ct.get_team(building_id)
        if not same_team:
            if etype in TURRETS:
                self.turrets_in_range.append((tile, etype, self.ct.get_direction(building_id)))
            elif etype == EntityType.LAUNCHER:
                self.enemy_launchers.add(tile)
            else:
                self.evaluate_aggressor_target(tile, building_id, bot_id, etype)
        
        if self.current_state == BotState.GOING_TO_TARGET and tile == self.current_target_position:
            if bot_id and bot_id != self.ct.get_id() and self.ct.get_team(bot_id) == self.ct.get_team():
                self.set_wandering()
            if building_id and etype not in PASSABLE:
                # Don't wander off if this is our own launcher we're trying to use
                if etype == EntityType.LAUNCHER and self.ct.get_team(building_id) == self.team:
                    pass
                else:
                    self.set_wandering()
    
    def unreachable_path(self):
        # Check if we already have a launcher built
        if self.own_launcher_pos is not None:
            own_launcher_id = self.ct.get_tile_building_id(self.own_launcher_pos) if checkable_position(self.own_launcher_pos, self.ct) else None
            own_launcher_exists = (
                own_launcher_id and
                self.ct.get_entity_type(own_launcher_id) == EntityType.LAUNCHER and
                self.ct.get_team(own_launcher_id) == self.team
            )

            if own_launcher_exists:
                # Launcher idle too long; no nearby targets, destroy and reset
                if self.rounds_without_launch >= 3:
                    if self.ct.can_destroy(self.own_launcher_pos):
                        self.ct.destroy(self.own_launcher_pos)
                    self.own_launcher_pos = None
                    self.rounds_without_launch = 0
                else:
                    self.rounds_without_launch += 1
                    self.set_target(self.own_launcher_pos, 2, BotState.GOING_TO_TARGET)
            else:
                # Launcher is gone, reset
                self.own_launcher_pos = None
                self.rounds_without_launch = 0

        # Try to place a new launcher if we don't have one
        if self.own_launcher_pos is None:
            launcher_pos = self._try_build_launcher()
            if launcher_pos:
                self.own_launcher_pos = launcher_pos
                self.rounds_without_launch = 0
                self.set_target(launcher_pos, 2, BotState.GOING_TO_TARGET)

    def nearest_unexplored(self) -> Position | None:
        target_pos_x = None
        target_pos_y = None
        if self.enemy_base_pos:
            target_pos_x = self.enemy_base_pos.x
            target_pos_y = self.enemy_base_pos.y
            
        else:
            w = self.map_width - 1
            h = self.map_height - 1

            target_pos_x = (2 * w - self.base_position.x) // 3
            target_pos_y = (2 * h - self.base_position.y) // 3

            
        return limit_to_map(
                Position(target_pos_x + random.randint(-5, 5),
                        target_pos_y + random.randint(-5, 5)),
                        self.ct
            )

    def reached_target(self):
        if self.current_state == BotState.WANDERING:
            self.set_target(self.nearest_unexplored(), 16, BotState.WANDERING)
            return
        
        if self.own_launcher_pos is None and self.ct.can_fire(self.position):
            self.ct.fire(self.position)

        can_build = self.ct.get_global_resources()[0] >= self.ct.get_sentinel_cost()[0]
        if can_build and self.enemy_base_pos:
            self.move_to_adjacent()
            if self.ct.can_build_sentinel(self.position, self.position.direction_to(self.enemy_base_pos)):
                self.ct.build_sentinel(self.position, self.position.direction_to(self.enemy_base_pos))

    def evaluate_aggressor_target(self, tile: Position, building_id, bot_id, entity_type):
        def evaluate_harvesters():
            for d in DIRECTIONS:
                check_pos = tile.add(d)
                if not checkable_position(check_pos, self.ct):
                    continue
                b_entity = get_entity(check_pos, self.ct)
                if b_entity in IGNORED_BUILDINGS or is_team_road(check_pos, self.ct):
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
        
        if entity_type == EntityType.HARVESTER:
            evaluate_harvesters()
        elif entity_type in CONVEYORS:
            evaluate_conveyors()

    def _try_build_launcher(self):
        print("Yo I need a launcher here")
        print(f"State {self.current_state}, targetted {self.current_target_position}")
        building_id = self.ct.get_tile_building_id(self.position)
        if building_id and self.ct.get_team(building_id) != self.team:
            if self.ct.can_fire(self.position):
                self.ct.fire(self.position)
        
        if is_team_road(self.position, self.ct):
            if self.ct.can_destroy(self.position):
                self.ct.destroy(self.position)
        
        can_build = self.ct.get_global_resources()[0] >= self.ct.get_launcher_cost()[0] and self.ct.get_action_cooldown() == 0
        if can_build:
            self.move_to_adjacent()
            if self.ct.can_build_launcher(self.position):
                self.ct.build_launcher(self.position)
                return self.position
        