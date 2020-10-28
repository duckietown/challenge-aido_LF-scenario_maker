#!/usr/bin/env python3
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

import geometry as g
import numpy as np
import yaml
from geometry import SE2value
from zuper_commons.logs import ZLogger
from zuper_nodes_wrapper import Context, wrap_direct

import duckietown_world as dw
from aido_schemas import (
    protocol_scenario_maker,
    RobotConfiguration,
    RobotName,
    Scenario,
    ScenarioRobotSpec,
)
from aido_schemas.protocol_simulator import MOTION_MOVING, MOTION_PARKED
from duckietown_world import list_maps
from duckietown_world.world_duckietown.map_loading import _get_map_yaml
from duckietown_world.world_duckietown.sampling_poses import sample_good_starting_pose

logger = ZLogger(__name__)
__version__ = "6.0.4"
logger.info(f"{__version__}")


@dataclass
class MyScenario(Scenario):
    scenario_name: str
    environment: str
    robots: Dict[str, ScenarioRobotSpec]


@dataclass
class MyConfig:
    maps: Tuple[str, ...] = ("4way",)
    scenarios_per_map: int = 1
    theta_tol_deg: float = 20.0
    dist_tol_m: float = 0.05
    min_dist: float = 0.5
    only_straight: bool = True
    robots_npcs: List[str] = ("npc1", "npc2", "npc3")
    robots_pcs: List[str] = ("ego",)
    robots_parked: List[str] = ("parked0",)


@dataclass
class MyState:
    scenarios_to_go: List[MyScenario]


def update_map(yaml_data):
    tiles = yaml_data["tiles"]

    for row in tiles:
        for i in range(len(row)):
            row[i] = row[i].replace("asphalt", "floor")


class SimScenarioMaker:
    config: MyConfig = MyConfig()
    state: MyState = MyState([])

    def init(self, context: Context):
        pass

    def _create_scenarios(self, context: Context):
        available = list_maps()

        for map_name in self.config.maps:
            if not map_name in available:
                msg = f'Cannot find map name "{map_name}, know {available}'
                raise Exception(msg)

            s: str = _get_map_yaml(map_name)

            config = self.config

            # yaml_str = update_map(yaml_str)

            yaml_data = yaml.load(s, Loader=yaml.SafeLoader)
            update_map(yaml_data)
            yaml_str = yaml.dump(yaml_data)

            delta_theta_rad = np.deg2rad(config.theta_tol_deg)
            only_straight = config.only_straight
            min_dist = config.min_dist
            delta_y_m = config.dist_tol_m

            for imap in range(self.config.scenarios_per_map):
                scenario_name = f"{map_name}-{imap}"

                ms = make_scenario(
                    yaml_str=yaml_str,
                    only_straight=only_straight,
                    min_dist=min_dist,
                    delta_y_m=delta_y_m,
                    robots_parked=config.robots_parked,
                    robots_pcs=config.robots_pcs,
                    robots_npcs=config.robots_npcs,
                    delta_theta_rad=delta_theta_rad,
                    scenario_name=scenario_name,
                )
                self.state.scenarios_to_go.append(ms)

    def on_received_seed(self, context: Context, data: int):
        context.info(f"seed({data})")
        np.random.seed(data)
        random.seed(data)

        self._create_scenarios(context)

    def on_received_next_scenario(self, context: Context):
        if self.state.scenarios_to_go:
            scenario = self.state.scenarios_to_go.pop(0)
            context.write("scenario", scenario)
        else:
            context.write("finished", None)

    def finish(self, context: Context):
        pass


def make_scenario(
    yaml_str: str,
    scenario_name: str,
    only_straight: bool,
    min_dist: float,
    delta_y_m: float,
    delta_theta_rad: float,
    robots_pcs: List[RobotName],
    robots_npcs: List[RobotName],
    robots_parked: List[RobotName],
) -> MyScenario:
    yaml_data = yaml.load(yaml_str, Loader=yaml.SafeLoader)
    po = dw.construct_map(yaml_data)
    num_pcs = len(robots_pcs)
    num_npcs = len(robots_npcs)
    num_parked = len(robots_parked)
    nrobots = num_npcs + num_pcs + num_parked

    poses = sample_many_good_starting_poses(
        po,
        nrobots,
        only_straight=only_straight,
        min_dist=min_dist,
        delta_theta_rad=delta_theta_rad,
        delta_y_m=delta_y_m,
    )

    poses_pcs = poses[:num_pcs]
    poses = poses[num_pcs:]
    #
    poses_npcs = poses[:num_npcs]
    poses = poses[num_npcs:]
    #
    poses_parked = poses[:num_parked]
    poses = poses[num_parked:]
    assert len(poses) == 0

    robots = {}
    for i, robot_name in enumerate(robots_pcs):
        pose = poses_pcs[i]
        vel = g.se2_from_linear_angular([0, 0], 0)

        configuration = RobotConfiguration(pose=pose, velocity=vel)

        robots[robot_name] = ScenarioRobotSpec(
            description=f"Playable robot {robot_name}",
            playable=True,
            configuration=configuration,
            motion=None,
        )

    for i, robot_name in enumerate(robots_npcs):
        pose = poses_npcs[i]
        vel = g.se2_from_linear_angular([0, 0], 0)

        configuration = RobotConfiguration(pose=pose, velocity=vel)

        robots[robot_name] = ScenarioRobotSpec(
            description=f"NPC robot {robot_name}",
            playable=False,
            configuration=configuration,
            motion=MOTION_MOVING,
        )

    for i, robot_name in enumerate(robots_parked):
        pose = poses_parked[i]
        vel = g.se2_from_linear_angular([0, 0], 0)

        configuration = RobotConfiguration(pose=pose, velocity=vel)

        robots[robot_name] = ScenarioRobotSpec(
            description=f"Parked robot {robot_name}",
            playable=False,
            configuration=configuration,
            motion=MOTION_PARKED,
        )

    ms = MyScenario(scenario_name=scenario_name, environment=yaml_str, robots=robots)
    return ms


def sample_many_good_starting_poses(
    po: dw.PlacedObject,
    nrobots: int,
    only_straight: bool,
    min_dist: float,
    delta_theta_rad: float,
    delta_y_m: float,
) -> List[np.ndarray]:
    poses = []

    def far_enough(pose_):
        for p in poses:
            if distance_poses(p, pose_) < min_dist:
                return False
        return True

    while len(poses) < nrobots:
        pose = sample_good_starting_pose(po, only_straight=only_straight)
        if far_enough(pose):
            theta = np.random.uniform(-delta_theta_rad, +delta_theta_rad)
            y = np.random.uniform(-delta_y_m, +delta_y_m)
            t = [0, y]
            q = g.SE2_from_translation_angle(t, theta)
            pose = g.SE2.multiply(pose, q)
            poses.append(pose)
    return poses


def distance_poses(q1: SE2value, q2: SE2value) -> float:
    SE2 = g.SE2
    d = SE2.multiply(SE2.inverse(q1), q2)
    t, _a = g.translation_angle_from_SE2(d)
    return np.linalg.norm(t)


def main():
    node = SimScenarioMaker()
    protocol = protocol_scenario_maker
    protocol.outputs["scenario"] = MyScenario
    wrap_direct(node=node, protocol=protocol)


if __name__ == "__main__":
    main()
