from cambc import Direction, EntityType, Environment
from enum import Enum

DIRECTIONS = {Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST, Direction.NORTHEAST, Direction.NORTHWEST, Direction.SOUTHEAST, Direction.SOUTHWEST}
ALL_DIRECTIONS = {Direction.CENTRE, Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST, Direction.NORTHEAST, Direction.NORTHWEST, Direction.SOUTHEAST, Direction.SOUTHWEST}
CARDINAL_DIRECTIONS = {Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST}
DIAGONAL_DIRECTIONS = {Direction.NORTHEAST, Direction.NORTHWEST, Direction.SOUTHEAST, Direction.SOUTHWEST}
PASSABLE = {None, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ROAD, EntityType.ARMOURED_CONVEYOR, EntityType.BUILDER_BOT, EntityType.CORE, EntityType.MARKER, EntityType.SPLITTER}
VALUABLE_ENEMY_ENTITIES = {EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE, EntityType.FOUNDRY, EntityType.BUILDER_BOT, EntityType.CORE, EntityType.GUNNER, EntityType.SENTINEL, EntityType.BREACH}
VALUABLE_ENEMY_ENTITIES_ORDERED = [
    EntityType.CONVEYOR,
    EntityType.ARMOURED_CONVEYOR,
    EntityType.SPLITTER,
    EntityType.BRIDGE,
    EntityType.LAUNCHER,
    EntityType.FOUNDRY,
    EntityType.BUILDER_BOT,
    EntityType.CORE,
    EntityType.GUNNER,
    EntityType.SENTINEL,
]
ORE_SITES = {Environment.ORE_TITANIUM, Environment.ORE_AXIONITE}
CONVEYORS = {EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER}
CONVEYORS_WITHOUT_SPLITTER = {EntityType.CONVEYOR, EntityType.BRIDGE, EntityType.ARMOURED_CONVEYOR}
INVALID_CONTAINERS = {EntityType.MARKER, EntityType.ROAD, None}
DESTROYABLE_BUILDINGS = {EntityType.BARRIER}
STUCK_THRESHHOLD = 3
TURRETS = {EntityType.SENTINEL, EntityType.GUNNER, EntityType.BREACH}
IGNORED_BUILDINGS = {EntityType.MARKER, None}
CAN_BUILD_OVER = {EntityType.MARKER, None, EntityType.ROAD}
CARDINAL_DELTAS = [
    (0, 1, 0.3), 
    (0, -1, 0.3), 
    (1, 0, 0.3), 
    (-1, 0, 0.3)
]
DIAGONAL_DELTAS = [
    (1, 1, 0.3), 
    (-1, -1, 0.3), 
    (1, -1, 0.3), 
    (-1, 1, 0.3)
]
ALL_DELTAS = CARDINAL_DELTAS + DIAGONAL_DELTAS
BRIDGE_PENALTY = 4
BRIDGE_DELTAS = [(dx, dy, BRIDGE_PENALTY) for dx in range(-3, 4) for dy in range(-3, 4) if 1 < dx*dx + dy*dy <= 9]
EXPLORE_TIMER = 12
DEMENTIA_RATE = 0.9
class BotState(Enum):
    GOING_TO_TARGET = 1
    WANDERING = 2
    GOING_BACK = 3

class DeltaTypes(Enum):
    CARDINAL = 0
    DIAGONAL = 1
    ALL = 2
    BRIDGE = 3

BASE_DIST = 18
FOUNDARY_THRESHHOLD = 600
class TargetTypes(Enum):
    CONNECT_BRIDGE = 0
    BASE = 1
    ORE = 2
    WANDER = 3
    REPAIR = 4
    AGG_HARVESTER = 5
    AGG_DISCONNECTED_CONVEYOR = 6
    REMOVAL = 7
    SENTINEL = 8

TURRET_THREAT_RADIUS = 2
_SENTINEL = object()

SENTINEL_RANGE = 26 # 5 ** 2

class PathfindStatus(Enum):
    SUCCESS = 0
    FAILURE = 1
    TIMEOUT = 2