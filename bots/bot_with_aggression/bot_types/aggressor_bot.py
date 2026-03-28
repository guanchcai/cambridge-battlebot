from bot_types.bot import Bot, BOT_STATE
from path_finder_two import flood_fill
from cambc import Team
from player_utils import *

class Aggressor(Bot):
    def __init__(self, ct):
        self.aggression_targets = []
        self.previous_pos = None
        self.blocking_jump_point = False
        super().__init__(ct)

    def _initialisation(self, ct):
        self.target_distance_squared = 9
        return super()._initialisation(ct)
    
    def _set_wandering(self):
        return super()._set_wandering()
    
    def _set_internal_map(self, position):
        return super()._set_internal_map(position)
    
    def _move_to_pos(self, ct: Controller):
        position = ct.get_position()
        if self.blocking_jump_point:
            self.blocking_jump_point = False
            bot_id = ct.get_tile_builder_bot_id(self.previous_pos)
            building_id = ct.get_tile_building_id(self.previous_pos)
            if bot_id is None and (building_id is None or ct.get_entity_type(building_id) in [EntityType.ROAD, EntityType.MARKER]):
                if ct.can_destroy(self.previous_pos):
                    ct.destroy(self.previous_pos)
                if ct.can_build_barrier(self.previous_pos):
                    ct.build_barrier(self.previous_pos)
                    return

        # Check if target is still valid
        if self.current_state == BOT_STATE.GOING_TO_TARGET:
            if is_in_bound(self.current_target_pos, ct) and ct.is_in_vision(self.current_target_pos):
                check_id = ct.get_tile_building_id(self.current_target_pos)
                b_id = ct.get_tile_builder_bot_id(self.current_target_pos)
                if ((check_id is not None or b_id is not None) and ct.get_entity_type(check_id) not in PASSABLE) or \
                    ct.get_tile_env(self.current_target_pos) == Environment.WALL or \
                    check_for_entity(self.current_target_pos, DIRECTIONS, EntityType.LAUNCHER, ct, other_team(ct)) is not None:
                    self._set_wandering()

        if self.current_state == BOT_STATE.GOING_TO_TARGET:
            dist = get_skibidi_distance(self.current_target_pos, ct.get_position())
            building_id = ct.get_tile_building_id(self.current_target_pos) if ct.is_in_vision(self.current_target_pos) else None
            if building_id and connected_to(self.current_target_pos, building_id, EntityType.SENTINEL, False, ct):
                self._pick_random(ct)

            if dist == 0:
                if (
                    building_id and 
                    ct.get_team(building_id) != ct.get_team() and
                    ct.can_fire(self.current_target_pos)
                ):
                    ct.fire(self.current_target_pos)
                
                building_id = ct.get_tile_building_id(self.current_target_pos)
                if (
                    building_id is None or 
                    (
                        (
                            ct.get_entity_type(building_id) == EntityType.ROAD or
                            ct.get_entity_type(building_id) in CONVEYORS
                        ) and 
                        ct.get_team(building_id) == ct.get_team()
                    )
                ) and (
                    ct.get_action_cooldown() == 0 and ct.get_global_resources()[0] >= ct.get_sentinel_cost()[0]
                ):
                    self._pick_random(ct, CARDINAL_DIRECTIONS)
            elif dist == 1:
                if ct.get_action_cooldown() == 0 and ct.get_global_resources()[0] >= ct.get_sentinel_cost()[0]:
                    if ((
                            ct.get_entity_type(building_id) == EntityType.ROAD or
                            ct.get_entity_type(building_id) in CONVEYORS
                        ) and 
                        ct.get_team(building_id) == ct.get_team()
                    ):
                        ct.destroy(self.current_target_pos)
                    building_id = ct.get_tile_building_id(self.current_target_pos)
                    if (
                        building_id is None
                    ):
                        self.build_sentinel(self.current_target_pos, self.current_target_pos.direction_to(self.enemy_pos), ct)
                        self._set_wandering()
                        return
        super()._move_to_pos(ct)

        if position and position != ct.get_position():
            if self.is_choke_point(position, ct):
                self.blocking_jump_point = True
                self.previous_pos = position
                return
    
    def _build_road(self, ct, move_pos, next_direction = None):
        if ct.can_build_road(move_pos):
            ct.build_road(move_pos)

    def update_map(self, ct):
        self.aggression_targets = []
        super().update_map(ct)
        if self.aggression_targets and self.current_state != BOT_STATE.GOING_TO_TARGET:
            random_target = random.choice(self.aggression_targets)
            self.current_target_pos = random_target
            self.target_distance_squared = 0
            self.current_state = BOT_STATE.GOING_TO_TARGET
            self.distance_map = None
    
    def _update_tile(self, tile, building_id, ct):

        # Building sentinels next to harvesters
        if building_id and ct.get_entity_type(building_id) == EntityType.HARVESTER and tile.distance_squared(self.enemy_pos) <= 13 ** 2:
            if self.current_state == BOT_STATE.WANDERING and tile != self.previous_target_pos:
                for d in CARDINAL_DIRECTIONS:
                    check_pos = tile.add(d)
                    if not (ct.is_in_vision(check_pos) and is_in_bound(check_pos, ct)):
                        continue
                    check_id = ct.get_tile_building_id(check_pos)
                    if (
                        check_id is None or 
                        (
                            ct.get_entity_type(check_id) in PASSABLE and 
                            not connected_to(tile, building_id, EntityType.SENTINEL, False, ct) 
                        )
                    ) and check_for_entity(check_pos, DIRECTIONS, EntityType.LAUNCHER, ct, other_team(ct)) is None:
                        if check_pos.distance_squared(self.enemy_pos) < 169:
                            self.current_target_pos = check_pos
                            self.target_distance_squared = 0
                            self.current_state = BOT_STATE.GOING_TO_TARGET
                            self.distance_map = None
        # Hijacking enemy conveyor chain
        elif building_id and ct.get_entity_type(building_id) in CONVEYORS and ct.get_stored_resource(building_id) in [ResourceType.REFINED_AXIONITE, ResourceType.TITANIUM] and tile.distance_squared(self.enemy_pos) <= 13 ** 2:
            targetted_pos = get_targetted_pos(tile, ct)
            has_launcher = (
                check_for_entity(tile, DIRECTIONS, EntityType.LAUNCHER, ct, other_team(ct)) is not None or
                (targetted_pos and check_for_entity(targetted_pos, DIRECTIONS, EntityType.LAUNCHER, ct, other_team(ct)) is not None)
            )
            if (
                self.current_state == BOT_STATE.WANDERING and
                tile != self.previous_target_pos and
                not has_launcher and
                not connected_to(tile, building_id, EntityType.SENTINEL, False, ct) and
                not pointed_towards_bot(tile, building_id, ct)
            ):
                targetted_id = ct.get_tile_building_id(targetted_pos) if targetted_pos else None
                if targetted_id and ct.get_team(building_id) != ct.get_team() and ct.get_entity_type(targetted_id) != EntityType.CORE:
                    self.aggression_targets.append(targetted_pos)
                else:
                    self.aggression_targets.append(tile)
                        
    def _read_markers(self, val, marker_pos):
        return super()._read_markers(val, marker_pos)
    
    def _find_target(self, ct):
        return self._nearest_unexplored(None, ct)
    
    def _hit_wall(self, wall_pos, ct):
        print("I hit a wall!")
        bot_id = ct.get_tile_builder_bot_id(wall_pos)
        if bot_id:
            self._pick_random(ct)
        self.distance_map = None
    
    def _target_reached(self, ct):
        if self.current_state == BOT_STATE.WANDERING:
            self.current_target_pos = self._find_target(ct)
            self._move_to_pos(ct)
    
    def _nearest_unexplored(self, pos: Position, ct: Controller) -> Position | None:
        return limit(Position(self.enemy_pos.x + random.randint(-5, 5), self.enemy_pos.y + random.randint(-5, 5)), ct)
        
    def build_sentinel(self, p: Position, d: Direction, ct: Controller):
        harvester_pos = check_for_entity(p, CARDINAL_DIRECTIONS, EntityType.HARVESTER, ct)

        if harvester_pos:
            if p.distance_squared(self.enemy_pos) >= 169 or check_for_entity(harvester_pos, CARDINAL_DIRECTIONS, EntityType.SENTINEL, ct, ct.get_team()):
                if ct.can_build_barrier(p):
                    ct.build_barrier(p)
                    self._set_wandering()
                return
            
        if ct.can_build_sentinel(p, d):
            building_id = ct.get_tile_building_id(p.add(d))
            if building_id and ct.get_entity_type(building_id) == EntityType.HARVESTER and d in CARDINAL_DIRECTIONS:
                d = d.rotate_left()
            ct.build_sentinel(p, d)
            self._set_wandering()
            return
        
    def is_choke_point(self, position: Position, ct: Controller) -> bool:
        def blocked(px, py):
            pos = Position(px, py)
            if not is_in_bound(pos, ct):
                return True  # out of bounds = impassable
            if not ct.is_in_vision(pos):
                return True  # treat unseen tiles as blocked
            b_id = ct.get_tile_building_id(pos)
            is_walled = (ct.get_tile_env(pos) == Environment.WALL) or \
                        (b_id and ct.get_entity_type(b_id) not in PASSABLE)
            return is_walled

        x, y = position.x, position.y

        # Cardinal choke points: walls on both sides of an axis
        if blocked(x, y + 1) and blocked(x, y - 1):
            return True
        if blocked(x + 1, y) and blocked(x - 1, y):
            return True

        # Diagonal choke: the two open diagonal tiles are the only passage
        if not blocked(x, y) and not blocked(x - 1, y - 1) \
                and blocked(x - 1, y) and blocked(x, y - 1):
            return True
        if not blocked(x, y) and not blocked(x - 1, y + 1) \
                and blocked(x - 1, y) and blocked(x, y + 1):
            return True
        if not blocked(x, y) and not blocked(x + 1, y + 1) \
                and blocked(x + 1, y) and blocked(x, y + 1):
            return True
        if not blocked(x, y) and not blocked(x + 1, y - 1) \
                and blocked(x + 1, y) and blocked(x, y - 1):
            return True

        return False