from entity_behaviour.bot import Bot
from utils.constants import *
from utils.helper_functions import *
from cambc import Controller, Position, Direction, EntityType, Environment
import random

class Aggressor(Bot):
    def __init__(self, ct: Controller):
        self.aggression_targets = []
        self.previous_pos = None
        self.blocking_jump_point = False
        super().__init__(ct)

    def set_wandering(self):
        self.aggression_targets = []
        super().set_wandering()

    def move_to_pos(self):
        position = self.ct.get_position()

        if self.blocking_jump_point:
            self.blocking_jump_point = False
            bot_id = self.ct.get_tile_builder_bot_id(self.previous_pos)
            building_id = self.ct.get_tile_building_id(self.previous_pos)
            if bot_id is None and (building_id is None or self.ct.get_entity_type(building_id) in [EntityType.ROAD, EntityType.MARKER]):
                if self.ct.can_destroy(self.previous_pos):
                    self.ct.destroy(self.previous_pos)
                if self.ct.can_build_barrier(self.previous_pos):
                    self.ct.build_barrier(self.previous_pos)
                    return

        if self.current_state == BotState.GOING_TO_TARGET:
            if is_in_bound(self.current_target_position, self.ct) and self.ct.is_in_vision(self.current_target_position):
                check_id = self.ct.get_tile_building_id(self.current_target_position)
                b_id = self.ct.get_tile_builder_bot_id(self.current_target_position)
                if ((check_id is not None or b_id is not None) and self.ct.get_entity_type(check_id) not in PASSABLE) or \
                    self.ct.get_tile_env(self.current_target_position) == Environment.WALL or \
                    check_for_entity(self.current_target_position, DIRECTIONS, EntityType.LAUNCHER, self.ct, other_team(self.ct)) is not None:
                    self.set_wandering()

        if self.current_state == BotState.GOING_TO_TARGET:
            dist = get_skibidi_distance(self.current_target_position, self.ct.get_position())
            building_id = self.ct.get_tile_building_id(self.current_target_position) if self.ct.is_in_vision(self.current_target_position) else None

            if building_id and connected_to(self.current_target_position, building_id, EntityType.SENTINEL, False, self.ct):
                self.set_wandering()

            if dist == 0:
                if (
                    building_id and
                    self.ct.get_team(building_id) != self.ct.get_team() and
                    self.ct.can_fire(self.current_target_position)
                ):
                    self.ct.fire(self.current_target_position)

                building_id = self.ct.get_tile_building_id(self.current_target_position)
                if ( building_id is None or
                    ( ( self.ct.get_entity_type(building_id) == EntityType.ROAD or
                        self.ct.get_entity_type(building_id) in CONVEYORS
                       ) and self.ct.get_team(building_id) == self.ct.get_team() )
                ) and (
                    self.ct.get_action_cooldown() == 0 and self.ct.get_global_resources()[0] >= self.ct.get_sentinel_cost()[0]
                ):
                    self.set_wandering()

            elif dist == 1:
                if self.ct.get_action_cooldown() == 0 and self.ct.get_global_resources()[0] >= self.ct.get_sentinel_cost()[0]:
                    if ((
                            self.ct.get_entity_type(building_id) == EntityType.ROAD or
                            self.ct.get_entity_type(building_id) in CONVEYORS
                        ) and
                        self.ct.get_team(building_id) == self.ct.get_team() and
                        self.ct.can_destroy(self.current_target_position)
                    ):
                        self.ct.destroy(self.current_target_position)
                    building_id = self.ct.get_tile_building_id(self.current_target_position)
                    if building_id is None:
                        self.build_sentinel(self.current_target_position, self.current_target_position.direction_to(self.enemy_pos), self.ct)
                        self.set_wandering()
                        return

        super().move_to_pos()

        b_id = self.ct.get_tile_building_id(self.ct.get_position())
        if b_id and self.ct.get_entity_type(b_id) in CONVEYORS and self.ct.get_team(b_id) != self.ct.get_team() and \
           self.ct.can_fire(self.ct.get_position()):
            self.ct.fire(self.ct.get_position())

        if position and position != self.ct.get_position():
            if self.is_choke_point(position, self.ct):
                self.blocking_jump_point = True
                self.previous_pos = position

    def build_road(self, move_pos: Position, next_pos: Position):
        if self.ct.can_build_road(move_pos):
            self.ct.build_road(move_pos)
        return True

    def update_map(self):
        self.aggression_targets = []
        super().update_map()
        if self.aggression_targets and self.current_state != BotState.GOING_TO_TARGET:
            random_target = random.choice(self.aggression_targets)
            self.set_target(random_target, 0, BotState.GOING_TO_TARGET)

    def update_tile(self, tile: Position, building_id: int | None, bot_id: int | None):
        if building_id and self.ct.get_entity_type(building_id) == EntityType.HARVESTER and tile.distance_squared(self.enemy_pos) <= 13 ** 2:
            if self.current_state == BotState.WANDERING and tile != self.previous_target_pos:
                for d in CARDINAL_DIRECTIONS:
                    check_pos = tile.add(d)
                    if not (self.ct.is_in_vision(check_pos) and is_in_bound(check_pos, self.ct)):
                        continue
                    check_id = self.ct.get_tile_building_id(check_pos)
                    if (check_id is None or
                        ( self.ct.get_entity_type(check_id) in PASSABLE and
                          not connected_to(tile, building_id, EntityType.SENTINEL, False, self.ct) )
                    ) and check_for_entity(check_pos, DIRECTIONS, EntityType.LAUNCHER, self.ct, other_team(self.ct)) is None:
                        if check_pos.distance_squared(self.enemy_pos) < 169:
                            self.set_target(check_pos, 0, BotState.GOING_TO_TARGET)

        elif building_id and self.ct.get_entity_type(building_id) in CONVEYORS and self.ct.get_stored_resource(building_id) in [ResourceType.REFINED_AXIONITE, ResourceType.TITANIUM] and tile.distance_squared(self.enemy_pos) <= 13 ** 2:
            targetted_pos = get_targetted_pos(tile, self.ct)
            has_launcher = (
                check_for_entity(tile, DIRECTIONS, EntityType.LAUNCHER, self.ct, other_team(self.ct)) is not None or
                (targetted_pos and check_for_entity(targetted_pos, DIRECTIONS, EntityType.LAUNCHER, self.ct, other_team(self.ct)) is not None)
            )
            if (
                self.current_state == BotState.WANDERING and
                tile != self.previous_target_pos and
                not has_launcher and
                not connected_to(tile, building_id, EntityType.SENTINEL, False, self.ct) and
                not pointed_towards_bot(tile, building_id, self.ct) and
                self.enemy_pos.distance_squared(tile) <= 13 ** 2
            ):
                targetted_id = self.ct.get_tile_building_id(targetted_pos) if targetted_pos else None
                if targetted_id and self.ct.get_team(building_id) != self.ct.get_team() and \
                   self.ct.get_entity_type(targetted_id) != EntityType.CORE:
                    self.aggression_targets.append(targetted_pos)
                else:
                    self.aggression_targets.append(tile)

    def nearest_unexplored(self) -> Position | None:
        return limit(
            Position(self.enemy_pos.x + random.randint(-5, 5),
                     self.enemy_pos.y + random.randint(-5, 5)),
                    self.ct
        )

    def reached_target(self):
        if self.current_state == BotState.WANDERING:
            self.current_target_position = self.nearest_unexplored()
            self.move_to_pos()

    def build_sentinel(self, p: Position, d: Direction, ct: Controller):
        harvester_pos = check_for_entity(p, CARDINAL_DIRECTIONS, EntityType.HARVESTER, ct)

        if harvester_pos:
            if p.distance_squared(self.enemy_pos) >= 169 or \
               check_for_entity(harvester_pos, CARDINAL_DIRECTIONS, EntityType.SENTINEL, ct, ct.get_team()):
                if ct.can_build_barrier(p):
                    ct.build_barrier(p)
                    self.set_wandering()
                return

        if ct.can_build_sentinel(p, d):
            building_id = ct.get_tile_building_id(p.add(d))
            if building_id and ct.get_entity_type(building_id) == EntityType.HARVESTER and d in CARDINAL_DIRECTIONS:
                d = d.rotate_left()