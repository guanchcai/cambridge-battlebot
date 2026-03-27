from bot_types.bot import Bot, BOT_STATE
from path_finder_two import flood_fill
from player_utils import *

class Aggressor(Bot):
    def __init__(self, ct):
        self.aggression_targets = []
        super().__init__(ct)

    def _initialisation(self, ct):
        self.target_distance_squared = 9
        return super()._initialisation(ct)
    
    def _set_wandering(self):
        return super()._set_wandering()
    
    def _set_internal_map(self, position):
        return super()._set_internal_map(position)
    
    def _move_to_pos(self, ct, allowed_movements=...):
        return super()._move_to_pos(ct)
        if self.current_state == BOT_STATE.GOING_TO_TARGET:
            dist = get_skibidi_distance(self.current_target_pos, ct.get_position())
            building_id = ct.get_tile_building_id(self.current_target_pos) if ct.is_in_vision(self.current_target_pos) else None
            if dist == 0:
                if (
                    building_id and 
                    ct.get_team(building_id) != ct.get_team() and
                    ct.can_fire(self.current_target_pos)
                ):
                    ct.fire(self.current_target_pos)
                
                b_id = ct.get_tile_building_id(self.current_target_pos)
                if (
                    b_id is None or 
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
        return super()._move_to_pos(ct)
    
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
        bot_id = ct.get_tile_builder_bot_id(tile)
        if bot_id:
            set_from_pos(self.internal_walkable_map, tile, Environment.WALL, self.map_width)

        if building_id and ct.get_entity_type(building_id) == EntityType.HARVESTER and tile.distance_squared(self.enemy_pos) <= 13 ** 2:
            if self.current_state == BOT_STATE.WANDERING:
                for d in CARDINAL_DIRECTIONS:
                    check_pos = tile.add(d)
                    if not (ct.is_in_vision(check_pos) and is_in_bound(check_pos, ct)):
                        continue
                    check_id = ct.get_tile_building_id(check_pos)
                    if (
                        check_id is None
                    ) or (
                        ct.get_entity_type(check_id) in PASSABLE and 
                        not connected_to(tile, building_id, EntityType.SENTINEL, False, ct)
                    ):
                        if check_pos.distance_squared(self.enemy_pos) < check_pos.distance_squared(self.original_pos):
                            self.current_target_pos = check_pos
                            self.target_distance_squared = 0
                            self.current_state = BOT_STATE.GOING_TO_TARGET
                            self.distance_map = None
        elif building_id and ct.get_entity_type(building_id) in CONVEYORS and ct.get_stored_resource(building_id) in [ResourceType.REFINED_AXIONITE, ResourceType.TITANIUM] and tile.distance_squared(self.enemy_pos) < tile.distance_squared(self.original_pos):
            if self.current_state == BOT_STATE.WANDERING and not connected_to(tile, building_id, EntityType.SENTINEL, False, ct):
                self.aggression_targets.append(tile)
        
        if self.current_state == BOT_STATE.GOING_TO_TARGET:
            if is_in_bound(self.current_target_pos, ct) and ct.is_in_vision(self.current_target_pos):
                check_id = ct.get_tile_building_id(self.current_target_pos)
                if check_id is not None and ct.get_entity_type(check_id) not in PASSABLE:
                    self._set_wandering()
                        
    def _read_markers(self, val, marker_pos):
        return super()._read_markers(val, marker_pos)
    
    def _find_target(self, ct):
        return self._nearest_unexplored(None, ct)
    
    def _hit_wall(self, wall_pos, ct):
        print("I hit a wall!")
        if get_from_pos(self.internal_walkable_map, wall_pos, self.map_width) != Environment.WALL:
            self._pick_random(ct)
            return
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