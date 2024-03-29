#!/usr/bin/env python3
import random
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np
import yaml
from zuper_commons.logs import ZLogger
from zuper_commons.types import ZException

from aido_schemas import (
    Context,
    PROTOCOL_FULL,
    PROTOCOL_NORMAL,
    protocol_scenario_maker,
    ProtocolDesc,
    Scenario,
    wrap_direct,
)
from duckietown_world.resources import list_maps
from duckietown_world.world_duckietown.map_loading import _get_map_yaml
from duckietown_world.world_duckietown.sampling import make_scenario

logger = ZLogger("scenario_maker")
__version__ = "6.0.34"
logger.info(f"{__version__}")


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
    nduckies: int = 0
    duckie_min_dist_from_other_duckie: float = 0.1
    duckie_min_dist_from_robot: float = 0.2
    duckie_y_bounds: List[float] = field(default_factory=lambda: [-0.1, 0.1])
    pc_robot_protocol: ProtocolDesc = PROTOCOL_NORMAL
    npc_robot_protocol: ProtocolDesc = PROTOCOL_FULL


@dataclass
class MyState:
    scenarios_to_go: List[Scenario]


def update_map1(yaml_data):
    tiles = yaml_data["tiles"]

    for row in tiles:
        for i in range(len(row)):
            row[i] = row[i].replace("asphalt", "floor")


def update_map2(yaml_data):
    tiles = yaml_data["tiles"]

    W = len(tiles[0])
    F = "floor"
    # noinspection PyListCreation
    tiles2 = []
    tiles2.append([F] * (W + 2))
    for row in tiles:
        row2 = [F] + row + [F]
        tiles2.append(row2)
    tiles2.append([F] * (W + 2))
    yaml_data["tiles"] = tiles2


class SimScenarioMaker:
    config: MyConfig = MyConfig()
    state: MyState = MyState([])

    def init(self, context: Context):
        pass

    def _create_scenarios(self, context: Context):
        available = list_maps()

        for map_name in self.config.maps:
            if not map_name in available:
                msg = f'Cannot find map name "{map_name}".'
                raise ZException(msg, available=available)

            s: str = _get_map_yaml(map_name)

            config = self.config

            yaml_data = yaml.load(s, Loader=yaml.SafeLoader)
            update_map1(yaml_data)
            # update_map1(yaml_data)
            yaml_str = yaml.dump(yaml_data)

            delta_theta_rad = np.deg2rad(config.theta_tol_deg)
            only_straight = config.only_straight
            min_dist = config.min_dist
            delta_y_m = config.dist_tol_m

            for imap in range(self.config.scenarios_per_map):
                scenario_name = f"{map_name}-sc{imap}"

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
                    nduckies=config.nduckies,
                    duckie_min_dist_from_other_duckie=config.duckie_min_dist_from_other_duckie,
                    duckie_min_dist_from_robot=config.duckie_min_dist_from_robot,
                    duckie_y_bounds=config.duckie_y_bounds,
                    tree_density=0.0,
                    tree_min_dist=0.2,
                )

                self.state.scenarios_to_go.append(ms)

            # logger.info(scenarios=self.state.scenarios_to_go)

    def on_received_seed(self, context: Context, data: int):
        context.info(f"seed({data})")
        np.random.seed(data)
        random.seed(data)

        self._create_scenarios(context)

    def on_received_next_scenario(self, context: Context):
        context.info("received_next_scenario")
        if self.state.scenarios_to_go:
            scenario = self.state.scenarios_to_go.pop(0)
            context.info("sent scenario")
            context.write("scenario", scenario)
        else:
            context.info("sent finished = True")
            context.write("finished", None)

    def finish(self, context: Context):
        context.info("finish.")


def main():
    node = SimScenarioMaker()
    protocol = protocol_scenario_maker
    protocol.outputs["scenario"] = Scenario
    wrap_direct(node=node, protocol=protocol)
    logger.info("Graceful exit of scenario_maker")


if __name__ == "__main__":
    main()
