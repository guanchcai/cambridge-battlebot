from cambc import Controller, Position, EntityType, Team
from utils.constants import *
from typing import overload
import random

@overload
def is_in_bound(pos: Position, ct: Controller) -> bool:
    w = ct.get_map_width()
    h = ct.get_map_height()
    return is_in_bound(pos, w, h)

@overload
def is_in_bound(pos: Position, w: int, h: int) -> bool:
    return 0 <= pos.x < w and 0 <= pos.y < h

@overload
def is_in_bound(x: int, y: int, w: int, h: int) -> bool:
    return 0 <= x < w and 0 <= y < h

def is_in_bound(*args) -> bool:
    if len(args) == 4:
        x, y, w, h = args
    elif len(args) == 3:
        pos, w, h = args
        x, y = pos.x, pos.y
    else:
        pos, ct = args
        x, y = pos.x, pos.y
        w, h = ct.get_map_width(), ct.get_map_height()
    return 0 <= x < w and 0 <= y < h

def checkable_position(pos: Position, ct: Controller) -> bool:
    return ct.is_in_vision(pos) and is_in_bound(pos, ct)

def direction_to_delta(direction_type: DeltaTypes) -> list[tuple[int, int, float]]:
    match direction_type:
        case DeltaTypes.ALL:
            return ALL_DELTAS
        case DeltaTypes.CARDINAL:
            return CARDINAL_DELTAS
        case DeltaTypes.BRIDGE:
            return BRIDGE_DELTAS
        case DeltaTypes.DIAGONAL:
            return DIAGONAL_DELTAS

def is_road(pos: Position, ct: Controller) -> bool:
    building_id = ct.get_tile_building_id(pos)
    return building_id and ct.get_entity_type(building_id) == EntityType.ROAD

def min_with_random_tiebreak(iterable, key=(lambda x: x)):
    it = iter(iterable)
    try:
        first = next(it)
    except StopIteration:
        return None

    candidates = [first]
    min_key = key(first)

    for x in it:
        k = key(x)
        if k < min_key:
            min_key = k
            candidates = [x]
        elif k == min_key:
            candidates.append(x)

    return random.choice(candidates)

def other_team(team: Team) -> Team:
    match team:
        case Team.A:
            Team.B
        case Team.B:
            Team.A

def check_for_entity(ct: Controller, directions: list[Direction], entity: EntityType, team: Team) -> Position:
    position = ct.get_position()
    for d in directions:
        check_pos = position.add(d)
        if not checkable_position(check_pos, ct):
            continue
        check_id = ct.get_tile_building_id(check_pos)
        check_entity = ct.get_entity_type(check_id) if check_id else None
        if check_entity == entity:
            if ct.get_team(check_id) == team:
                return check_pos
            

def check_for_env(ct: Controller, directions: list[Direction], env: Environment) -> Position:
    position = ct.get_position()
    for d in directions:
        check_pos = position.add(d)
        if not checkable_position(check_pos, ct):
            continue
        check_env = ct.get_tile_env(check_pos)
        if check_env == env:
            return check_pos

def get_entity(pos: Position, ct: Controller) -> EntityType | None:
    
    b_id = ct.get_tile_building_id(pos)
    return ct.get_entity_type(b_id) if b_id else None