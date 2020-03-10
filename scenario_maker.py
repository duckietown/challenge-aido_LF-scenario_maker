#!/usr/bin/env python3
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import yaml

import duckietown_world as dw
import geometry as g
from aido_schemas import (
    Context,
    protocol_scenario_maker,
    RobotConfiguration,
    Scenario,
    ScenarioRobotSpec,
    wrap_direct,
)
from duckietown_world import list_maps
from duckietown_world.world_duckietown.map_loading import _get_map_yaml
from duckietown_world.world_duckietown.sampling_poses import sample_good_starting_pose


@dataclass
class MyScenario(Scenario):
    scenario_name: str
    environment: str
    robots: Dict[str, ScenarioRobotSpec]


@dataclass
class MyConfig:
    maps: Tuple[str, ...] = ("4way",)
    scenarios_per_map: int = 1
    robots_npcs: int = 0
    robots_pcs: int = 1
    theta_tol_deg: float = 20.0
    dist_tol_m: float = 0.05
    min_dist: float = 0.5
    only_straight: bool = True


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

            # yaml_str = update_map(yaml_str)

            yaml_data = yaml.load(s, Loader=yaml.SafeLoader)
            update_map(yaml_data)
            yaml_str = yaml.dump(yaml_data)

            po = dw.construct_map(yaml_data)

            for imap in range(self.config.scenarios_per_map):
                scenario_name = f"{map_name}-{imap}"

                nrobots = self.config.robots_npcs + self.config.robots_pcs
                poses = sample_many_good_starting_poses(
                    po,
                    nrobots,
                    only_straight=self.config.only_straight,
                    min_dist=self.config.min_dist,
                    delta_theta_rad=np.deg2rad(self.config.theta_tol_deg),
                    delta_y_m=self.config.dist_tol_m,
                )

                poses_pcs = poses[: self.config.robots_pcs]
                poses_npcs = poses[self.config.robots_pcs :]

                robots = {}
                for i in range(self.config.robots_pcs):
                    pose = poses_pcs[i]
                    vel = g.se2_from_linear_angular([0, 0], 0)

                    robot_name = "ego" if i == 0 else "player%d" % i
                    configuration = RobotConfiguration(pose=pose, velocity=vel)

                    robots[robot_name] = ScenarioRobotSpec(
                        description="Playable robot",
                        playable=True,
                        configuration=configuration,
                    )

                for i in range(self.config.robots_npcs):
                    pose = poses_npcs[i]
                    vel = g.se2_from_linear_angular([0, 0], 0)

                    robot_name = "npc%d" % i
                    configuration = RobotConfiguration(pose=pose, velocity=vel)

                    robots[robot_name] = ScenarioRobotSpec(
                        description="NPC robot",
                        playable=False,
                        configuration=configuration,
                    )

                ms = MyScenario(
                    scenario_name=scenario_name, environment=yaml_str, robots=robots
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


def sample_many_good_starting_poses(
    po: dw.PlacedObject,
    nrobots: int,
    only_straight: bool,
    min_dist: float,
    delta_theta_rad: float,
    delta_y_m: float,
) -> List[np.ndarray]:
    poses = []

    def far_enough(pose):
        for p in poses:
            if distance_poses(p, pose) < min_dist:
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


def distance_poses(q1, q2):
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
