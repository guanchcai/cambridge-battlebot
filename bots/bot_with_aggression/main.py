from enum import Enum
from player_utils import *
from bot_types.initiator_bot import Initator
from bot_types.bot import Bot
from bot_types.aggressor_bot import Aggressor
from bot_types.healer import Healer
from bot_types.waller import Waller
import time
class BOT_TYPE(Enum):
    NORMAL = 1
    AGGRESSOR = 2
    INITIATORS = 3
    REPAIR = 4

SYMBOLS = {
    Environment.EMPTY: "  ",
    Environment.WALL:  "██",
}

TRANSGENDER_PROBABILITY = 0.15


class Player:
    def __init__(self):
        # Core variables
        self.num_spawned = 0
        self.bomber_spawned = 0
        self.spawn_queue = [Direction.SOUTH, Direction.NORTH, Direction.NORTHEAST]

        self.bot_type: Bot | None = None
        random.seed(time.time())

    def run(self, ct: Controller) -> None:
        map_height = ct.get_map_height()
        map_width = ct.get_map_width()
        position = ct.get_position()
        current_round = ct.get_current_round()
        harvester_cost = ct.get_harvester_cost()[0]
        global_resources = ct.get_global_resources()[0]
        etype = ct.get_entity_type()
        match etype:
            case EntityType.CORE:
                print(self.spawn_queue)
                if current_round == 100:
                    self.spawn_queue.append(Direction.NORTHEAST)
                if current_round == 10:
                    self.spawn_queue.append(Direction.NORTH)
                bot_id = ct.get_tile_builder_bot_id(position)
                if bot_id is None:
                    if ct.can_spawn(position):
                        ct.spawn_builder(position)
                        
                if self.spawn_queue:
                    direction = self.spawn_queue[0]
                    spawn_pos = position.add(direction)
                    if ct.can_spawn(spawn_pos) and global_resources >= harvester_cost * 1.5:
                        ct.spawn_builder(spawn_pos)
                        self.num_spawned += 1
                        self.spawn_queue.pop(0)
                        return
                if (
                    not self.spawn_queue and current_round >= 80 and
                    (
                        ct.get_current_round() >= 400 or # Go ham
                        global_resources >= harvester_cost * 1.5
                    )
                    and self.num_spawned <= 500
                ):
                    direction = random.choice(DIAGONAL_DIRECTIONS)
                    spawn_pos = ct.get_position().add(direction)
                    if ct.can_spawn(spawn_pos):
                        ct.spawn_builder(spawn_pos)
                        self.num_spawned += 1
                        return
            case EntityType.SENTINEL | EntityType.GUNNER:
                candidate = None
                
                for tile in ct.get_nearby_tiles():
                    if not ct.can_fire(tile):
                        continue
                    building_id = ct.get_tile_building_id(tile)
                    bot_id = ct.get_tile_builder_bot_id(tile)
                    if connected_to(tile, building_id, EntityType.SENTINEL, False, ct):
                        continue
                    entity_id = bot_id or building_id
                    if entity_id:
                        print(ct.get_entity_type(entity_id))
                    try:
                        if entity_id and ct.get_team(entity_id) != ct.get_team():
                            etype = ct.get_entity_type(entity_id)
                            value = VALUABLE_ENEMY_ENTITIES.index(etype) + 5 if etype in VALUABLE_ENEMY_ENTITIES else 3
                            if building_id and bot_id and ct.get_entity_type(building_id) == EntityType.CORE:
                                value = 1000
                            if (candidate is None or value > candidate[1]) and etype != EntityType.HARVESTER:
                                candidate = (entity_id, value, tile)
                    except Exception:
                        continue
                
                if candidate and ct.can_fire(candidate[2]):
                    ct.fire(candidate[2])
            case EntityType.BREACH:
                for tile in ct.get_nearby_tiles():
                    if ct.can_fire(tile):
                        ct.fire(tile)
                        return
            case EntityType.LAUNCHER:
                launch_target = None
                to_launch = None

                for b_id in ct.get_nearby_units(3):
                    if ct.get_entity_type(b_id) == EntityType.BUILDER_BOT:
                        if ct.get_team(b_id) != ct.get_team() and ct.get_position(b_id).distance_squared(position) <= 2:
                            to_launch = b_id
                            break
                
                if to_launch is not None:
                    for b_id in ct.get_nearby_buildings():
                        if ct.get_entity_type(b_id) not in PASSABLE:
                            continue
                        same_team = ct.get_team(b_id) == ct.get_team()
                        if ct.get_entity_type(b_id) in CONVEYORS and same_team:
                            continue
                        build_pos = ct.get_position(b_id)
                        if ct.can_launch(ct.get_position(to_launch), build_pos):
                            if launch_target is None or build_pos.distance_squared(position) > launch_target.distance_squared(position):
                                launch_target = build_pos
                print(to_launch, launch_target)
                if to_launch and launch_target:
                    ct.launch(ct.get_position(to_launch), launch_target)
            case EntityType.BUILDER_BOT:
                if not self.bot_type:
                    self.bot_type = self.decide_bot_type(position, ct)

                bot = self.bot_type

                bot.update_map(ct)
                print(f"I am {bot.current_state}")

                if bot.current_target_pos:
                    ct.draw_indicator_line(ct.get_position(), bot.current_target_pos, 1, 1, 1)
                    bot._move_to_pos(ct)
                else:
                    bot.current_target_pos = bot._find_target(ct)

                if ct.can_heal(position):
                    ct.heal(position)
    
    def decide_bot_type(self, position: Position, ct: Controller):
        core_pos = ct.get_position(ct.get_tile_building_id(position))
        if get_skibidi_distance(core_pos, position) == 1:
            if position.y < core_pos.y:
                return Waller(ct)
            return Initator(ct)
        elif get_skibidi_distance(core_pos, position) == 2:
            if ct.get_current_round() > 100 and random.random() <= TRANSGENDER_PROBABILITY:
                return Initator(ct)
            return Aggressor(ct)
        else:
            return Healer(ct)
    
    
    # def aggressor_script(self, ct: Controller):
        
    #     def build_sentinel(p: Position, d: Direction, dy=None):
    #         harvester_pos = check_for_entity(p, CARDINAL_DIRECTIONS, EntityType.HARVESTER, ct)

    #         if harvester_pos:
    #             if check_for_entity(harvester_pos, CARDINAL_DIRECTIONS, EntityType.SENTINEL, ct, ct.get_team()):
    #                 if ct.can_build_barrier(p):
    #                     ct.build_barrier(p)
    #                     reset_target()
    #                 return
                
    #         if ct.can_build_sentinel(p, d):
    #             building_id = ct.get_tile_building_id(p.add(d))
    #             if building_id and ct.get_entity_type(building_id) == EntityType.HARVESTER:
    #                 d = d.rotate_left()
    #             ct.build_sentinel(p, d)
    #             reset_target()
    #             return
            
    #     def reset_target():
    #         self.aggressor_has_target = False
    #         self.current_target_pos = None
    #         self.distance_map = None
    #         self.current_state = BOT_STATE.WANDERING
        
    #     position = ct.get_position()

    #     if not self.current_target_pos or self.current_state == BOT_STATE.WANDERING:
    #         self.current_target_pos = limit(Position(self.enemy_pos.x + random.randint(-5, 5), self.enemy_pos.y + random.randint(-5, 5)), ct)
        
    #         self.distance_map = None
    #         self.aggressor_has_target = False
    #         self.target_distance_squared = 4
    #         return

    #     building_id = ct.get_tile_building_id(self.current_target_pos) if ct.is_in_vision(self.current_target_pos) else None
        
    #     if (
    #         ct.is_in_vision(self.current_target_pos) and 
    #         building_id and
    #         ct.get_entity_type(building_id) not in PASSABLE
    #     ):
    #         reset_target()
    #         return
        
    #     if (
    #         building_id and 
    #         connected_to(self.current_target_pos, building_id, EntityType.SENTINEL, False, ct)
    #     ):
    #         reset_target()
    #         return

        # point_dir = self.current_target_pos.direction_to(self.enemy_pos)
        # can_build_sentinel = ct.get_global_resources()[0] >= ct.get_sentinel_cost()[0] and ct.get_action_cooldown() == 0
        # if self.aggressor_has_target:
            
        #     if self.current_target_pos == position:
        #         if building_id and ct.get_team(building_id) != ct.get_team():
        #             if ct.can_fire(position):
        #                 ct.fire(position)
        #                 if not ct.get_tile_building_id(position):
        #                     # We have destroyed the target
        #                     self._pick_random(ct)
        #                     return

        #     if (
        #         not building_id or (ct.get_entity_type(building_id) == EntityType.ROAD and ct.get_team(building_id) == ct.get_team()) and
        #         can_build_sentinel
        #     ):
        #         if ct.can_destroy(self.current_target_pos):
        #             ct.destroy(self.current_target_pos)

        #         if position == self.current_target_pos:
        #             self._pick_random(ct)
        #         build_sentinel(self.current_target_pos, point_dir)
            

    # def repair_script(self, ct: Controller):
    #     if self.current_target_pos and ct.is_in_vision(self.current_target_pos):
    #         if ct.can_destroy(self.current_target_pos) and ct.get_entity_type(ct.get_tile_building_id(self.current_target_pos)) != EntityType.SPLITTER:
    #             ct.destroy(self.current_target_pos)
    #         if ct.can_build_splitter(self.current_target_pos,
    #                                  dir_to_original := self.current_target_pos.direction_to(self.original_pos)):
    #             ct.build_splitter(self.current_target_pos, dir_to_original)
            
    #     for check_dir in CARDINAL_DIRECTIONS:
    #         check_pos = self.original_pos.add(check_dir).add(check_dir)
    #         if not is_in_bound(check_pos, ct) or not ct.is_in_vision(check_pos):
    #             continue
    #         building_id = ct.get_tile_building_id(check_pos)
    #         if ct.get_tile_env(check_pos) == Environment.WALL or (building_id and ct.get_team(building_id) != ct.get_team()):
    #             continue
    #         if not (building_id and ct.get_entity_type(building_id) == EntityType.SPLITTER):
    #             self.target_distance_squared = 1
    #             self.current_target_pos = check_pos
    #             self.distance_map = None
    #             self.current_state = BOT_STATE.GOING_TO_TARGET
    #             return
    #     self.current_target_pos = self.original_pos
    #     self.target_distance_squared = 0
    #     self.distance_map = None
    #     self.current_state = BOT_STATE.GOING_TO_TARGET

