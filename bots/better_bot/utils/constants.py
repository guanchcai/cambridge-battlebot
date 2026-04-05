from cambc import Direction, EntityType, Environment
from enum import Enum

DIRECTIONS = {Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST, Direction.NORTHEAST, Direction.NORTHWEST, Direction.SOUTHEAST, Direction.SOUTHWEST}
ALL_DIRECTIONS = {Direction.CENTRE, Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST, Direction.NORTHEAST, Direction.NORTHWEST, Direction.SOUTHEAST, Direction.SOUTHWEST}
CARDINAL_DIRECTIONS = {Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST}
DIAGONAL_DIRECTIONS = {Direction.NORTHEAST, Direction.NORTHWEST, Direction.SOUTHEAST, Direction.SOUTHWEST}
PASSABLE = {None, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ROAD, EntityType.ARMOURED_CONVEYOR, EntityType.BUILDER_BOT, EntityType.CORE, EntityType.MARKER, EntityType.SPLITTER}
VALUABLE_ENEMY_ENTITIES = {EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE, EntityType.FOUNDRY, EntityType.BUILDER_BOT, EntityType.CORE, EntityType.GUNNER, EntityType.SENTINEL}
ORE_SITES = {Environment.ORE_TITANIUM, Environment.ORE_AXIONITE}
CONVEYORS = {EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER}
INVALID_CONTAINERS = {EntityType.MARKER, EntityType.ROAD, None}
DESTROYABLE_BUILDINGS = {EntityType.ROAD, EntityType.BARRIER}
STUCK_THRESHHOLD = 3
TURRETS = {EntityType.SENTINEL, EntityType.GUNNER, EntityType.BREACH}
IGNORED_BUILDINGS = {EntityType.MARKER, None}
CARDINAL_DELTAS = [
    (0, 1, 1), 
    (0, -1, 1), 
    (1, 0, 1), 
    (-1, 0, 1)
]
DIAGONAL_DELTAS = [
    (1, 1, 1.1), 
    (-1, -1, 1.1), 
    (1, -1, 1.1), 
    (-1, 1, 1.1)
]
ALL_DELTAS = CARDINAL_DELTAS + DIAGONAL_DELTAS
BRIDGE_PENALTY = 5
BRIDGE_DELTAS = [(dx, dy, (BRIDGE_PENALTY if dx*dx + dy*dy != 1 else 1)) for dx in range(-3, 4) for dy in range(-3, 4) if 0 < dx*dx + dy*dy <= 9]

class BotState(Enum):
    GOING_TO_TARGET = 1
    WANDERING = 2
    GOING_BACK = 3

class DeltaTypes(Enum):
    CARDINAL = 0
    DIAGONAL = 1
    ALL = 2
    BRIDGE = 3

BASE_DIST = 20
FOUNDARY_THRESHHOLD = 600
class TargetTypes(Enum):
    CONNECT_BRIDGE = 0
    BASE = 1
    ORE = 2
     